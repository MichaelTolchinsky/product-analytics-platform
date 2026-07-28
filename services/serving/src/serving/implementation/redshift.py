import asyncio
import logging
from typing import Any

MAX_WAIT_SECONDS = 30
POLL_INTERVAL_SECONDS = 0.05  # 50ms — tight loop for serving latency

logger = logging.getLogger(__name__)


class RedshiftEngine:
    """QueryEngine backed by Redshift Serverless Data API.

    Uses execute_statement + describe_statement (poll) + get_statement_result.
    No persistent connection — each call is stateless over HTTPS.
    """

    def __init__(self, client: Any, workgroup: str, database: str) -> None:
        self._client = client
        self._workgroup = workgroup
        self._database = database

    async def run(self, sql: str) -> list[dict[str, Any]]:
        statement_id = await self._submit(sql)
        await self._poll(statement_id)
        return await self._fetch_results(statement_id)

    async def _submit(self, sql: str) -> str:
        response = await self._client.execute_statement(
            WorkgroupName=self._workgroup,
            Database=self._database,
            Sql=sql,
        )
        return response["Id"]

    async def _poll(self, statement_id: str) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + MAX_WAIT_SECONDS

        while True:
            if loop.time() > deadline:
                raise TimeoutError(
                    f"Redshift statement {statement_id} exceeded {MAX_WAIT_SECONDS}s"
                )

            response = await self._client.describe_statement(Id=statement_id)
            status = response["Status"]

            if status == "FINISHED":
                return
            if status in {"FAILED", "ABORTED"}:
                error = response.get("Error", "unknown")
                raise RuntimeError(f"Redshift statement {statement_id} {status}: {error}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def _fetch_results(self, statement_id: str) -> list[dict[str, Any]]:
        """Convert Data API column metadata + records into list of dicts."""
        response = await self._client.get_statement_result(Id=statement_id)
        columns = [col["name"] for col in response["ColumnMetadata"]]
        return [
            {columns[i]: field.get("stringValue") for i, field in enumerate(row)}
            for row in response["Records"]
        ]
