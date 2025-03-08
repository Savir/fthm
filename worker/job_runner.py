import asyncio
import json
import os
import random

import redis
import structlog

from tools import constants
from tools.kafka import produce_message, consume_messages

log = structlog.get_logger()
# Redis Configuration
REDIS_URL = "redis://redis:6379"
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

# Kafka Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", default="kafka:9092")


async def publish_task_status(task_id, status):
    """Publishes task status update to Redis Pub/Sub."""
    message = json.dumps({"task_id": task_id, "status": status})
    log.info("Task status change", task_id=task_id, new_status=status)
    await produce_message(constants.status_updates_topic, message)
    redis_client.set(str(task_id), status, ex=3_600)  # Update cache ASAP


async def _simulate_work(kafka_msg, *, job_name: str):
    task_data = json.loads(kafka_msg)
    log.info(f"Got message from Kafka topic '{job_name}'", task_data=task_data)
    task_id = task_data["task_id"]
    await publish_task_status(task_id, job_name)
    try:
        # Pretend to take some time:
        await asyncio.sleep(2)
        if random.randint(0, 10) == 0:
            raise Exception(f"boooooOOOOOOm in {job_name}!!!")
    except Exception:
        await publish_task_status(task_id, constants.failed_status)
        raise


async def process_jobA():
    """Kafka consumer for JobA."""
    async for message in consume_messages(constants.start_topic):
        await _simulate_work(message, job_name="jobA")
        await produce_message("jobB", message)


async def process_jobB():
    """Kafka consumer for JobB."""
    async for message in consume_messages("jobB"):
        await _simulate_work(message, job_name="jobB")
        await produce_message("jobC", message)


async def process_jobC():
    """Kafka consumer for JobC."""
    async for message in consume_messages("jobC"):
        await _simulate_work(message, job_name="jobC")
        # Mark completed
        task_data = json.loads(message)
        await publish_task_status(task_data["task_id"], constants.completed_status)


async def main():
    """Run job consumers concurrently."""
    await asyncio.gather(process_jobA(), process_jobB(), process_jobC())


if __name__ == "__main__":
    log.info("Starting processing Kafka messages.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        log.info("Shutting down gracefully...")
    finally:
        loop.close()
