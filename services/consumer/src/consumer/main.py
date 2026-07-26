import asyncio
import logging

import aioboto3

from consumer.config import ConsumerSettings
from consumer.domain.batcher import EventBatcher
from consumer.domain.service import ConsumerService
from consumer.implementation.kinesis import KinesisReader
from consumer.implementation.s3_checkpoint import S3CheckpointStore
from consumer.implementation.s3_parquet import S3ParquetWriter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run() -> None:
    settings = ConsumerSettings()
    session = aioboto3.Session()

    async with (
        session.client(
            "kinesis", region_name=settings.aws_region, endpoint_url=settings.aws_endpoint_url
        ) as kinesis_client,
        session.client(
            "s3", region_name=settings.aws_region, endpoint_url=settings.aws_endpoint_url
        ) as s3_client,
    ):
        shards = await kinesis_client.list_shards(StreamName=settings.kinesis_stream_name)
        shard_id = shards["Shards"][0]["ShardId"]  # v1: single-shard stream

        checkpoint = S3CheckpointStore(
            client=s3_client,
            bucket=settings.s3_bucket,
            shard_id=shard_id,
        )
        reader = KinesisReader(
            client=kinesis_client,
            stream_name=settings.kinesis_stream_name,
            shard_id=shard_id,
            checkpoint=checkpoint,
        )
        writer = S3ParquetWriter(client=s3_client, bucket=settings.s3_bucket)
        batcher = EventBatcher(
            max_size=settings.batch_max_size,
            max_interval_seconds=settings.batch_max_interval_seconds,
        )
        service = ConsumerService(
            reader=reader,
            writer=writer,
            batcher=batcher,
            poll_interval_seconds=settings.poll_interval_seconds,
        )

        logger.info("consumer starting on shard %s", shard_id)
        await service.run_forever()


if __name__ == "__main__":
    asyncio.run(run())
