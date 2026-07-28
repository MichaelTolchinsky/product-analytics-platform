import json
import logging
from typing import Any

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# DynamoDB attribute names
_KEY_ATTR = "cache_key"
_VAL_ATTR = "cache_value"


class DynamoDBCache:
    """CacheStore backed by DynamoDB with native TTL.

    Table schema (created by scripts/bootstrap_local.py):
        PK: cache_key (S)
        Attribute: cache_value (S) — JSON-serialised payload
        TTL attribute: ttl (N) — Unix epoch seconds

    Falls through silently on any AWS error so the domain can
    always fall back to Redshift.
    """

    def __init__(self, client: Any, table_name: str) -> None:
        self._client = client
        self._table = table_name

    async def get(self, key: str) -> list[dict[str, Any]] | dict[str, Any] | None:
        try:
            response = await self._client.get_item(
                TableName=self._table,
                Key={_KEY_ATTR: {"S": key}},
            )
        except ClientError:
            logger.warning("DynamoDB get failed for key=%s — cache miss", key)
            return None

        item = response.get("Item")
        if item is None:
            return None

        try:
            return json.loads(item[_VAL_ATTR]["S"])
        except (KeyError, json.JSONDecodeError):
            logger.warning("DynamoDB item malformed for key=%s — cache miss", key)
            return None

    async def set(
        self,
        key: str,
        value: list[dict[str, Any]] | dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        import time

        expires_at = int(time.time()) + ttl_seconds
        try:
            await self._client.put_item(
                TableName=self._table,
                Item={
                    _KEY_ATTR: {"S": key},
                    _VAL_ATTR: {"S": json.dumps(value)},
                    "ttl": {"N": str(expires_at)},
                },
            )
        except ClientError:
            logger.warning("DynamoDB set failed for key=%s — write skipped", key)
