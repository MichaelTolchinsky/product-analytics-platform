import io
import json
import uuid
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from analytics_platform import Event


class S3ParquetWriter:
    """Writes a batch of events as a new Parquet object under bronze/<partition>/.

    Never overwrites — Parquet is immutable, so every flush is a new file.
    Bronze is expected to contain duplicates (at-least-once delivery);
    silver is the dedupe boundary.
    """

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def write_partition(self, events: list[Event], partition: str) -> None:
        table = self._to_table(events)

        buffer = io.BytesIO()
        pq.write_table(table, buffer)

        key = f"bronze/{partition}/{uuid.uuid4()}.parquet"
        await self._client.put_object(Bucket=self._bucket, Key=key, Body=buffer.getvalue())

    @staticmethod
    def _to_table(events: list[Event]) -> pa.Table:
        # metadata is free-form (dict[str, Any]); stored as a JSON string so
        # the Parquet schema stays stable regardless of what callers put in it.
        rows = []
        for event in events:
            row = event.model_dump(mode="json")
            row["metadata"] = json.dumps(row["metadata"])
            rows.append(row)
        return pa.Table.from_pylist(rows)
