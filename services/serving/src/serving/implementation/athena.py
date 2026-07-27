import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any

MAX_WAIT_SECONDS = 30  # metrics queries over small gold tables should be fast


class AthenaEngine:
    """QueryEngine backed by Athena — reads from gold tables in S3."""

    def __init__(self, client: Any, database: str, output_location: str) -> None:
        self._client = client
        self._database = database
        self._output_location = output_location

    async def run(self, sql: str) -> list[dict[str, Any]]:
        query_id = await self._submit(sql)
        await self._poll(query_id)
        return await self._fetch_results(query_id)

    async def _submit(self, sql: str) -> str:
        current_hour = datetime.now(UTC).strftime("%Y%m%d%H")
        token = hashlib.sha256(f"{sql}{current_hour}".encode()).hexdigest()[:128]

        response = await self._client.start_query_execution(
            QueryString=sql,
            ClientRequestToken=token,
            QueryExecutionContext={"Database": self._database},
            ResultConfiguration={"OutputLocation": self._output_location},
        )
        return response["QueryExecutionId"]

    async def _poll(self, query_id: str) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + MAX_WAIT_SECONDS

        while True:
            if loop.time() > deadline:
                raise TimeoutError(f"Athena query {query_id} exceeded {MAX_WAIT_SECONDS}s")

            status = await self._client.get_query_execution(QueryExecutionId=query_id)
            state = status["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                return
            if state in {"FAILED", "CANCELLED"}:
                reason = status["QueryExecution"]["Status"].get("StateChangeReason", "unknown")
                raise RuntimeError(f"Athena query {query_id} {state}: {reason}")

            await asyncio.sleep(1)

    async def _fetch_results(self, query_id: str) -> list[dict[str, Any]]:
        """Convert Athena's column/row format into a list of dicts."""
        response = await self._client.get_query_results(QueryExecutionId=query_id)
        rows = response["ResultSet"]["Rows"]

        if not rows:
            return []

        # First row is the column headers
        headers = [col["VarCharValue"] for col in rows[0]["Data"]]
        return [
            {headers[i]: col.get("VarCharValue") for i, col in enumerate(row["Data"])}
            for row in rows[1:]
        ]
