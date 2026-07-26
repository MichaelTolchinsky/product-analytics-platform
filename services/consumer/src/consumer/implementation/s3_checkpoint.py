import json
from typing import Any


class S3CheckpointStore:
    """Persists the last committed Kinesis sequence number to S3.

    Survives process restarts (task replacement, crash) without needing a
    separate coordination service (e.g. DynamoDB) for this single-shard,
    single-consumer v1 design.
    """

    def __init__(self, client: Any, bucket: str, shard_id: str) -> None:
        self._client = client
        self._bucket = bucket
        self._key = f"_checkpoints/{shard_id}.json"

    async def load(self) -> str | None:
        try:
            resp = await self._client.get_object(Bucket=self._bucket, Key=self._key)
        except self._client.exceptions.NoSuchKey:
            return None

        body = await resp["Body"].read()
        return json.loads(body)["sequence_number"]

    async def save(self, sequence_number: str) -> None:
        body = json.dumps({"sequence_number": sequence_number}).encode("utf-8")
        await self._client.put_object(Bucket=self._bucket, Key=self._key, Body=body)
