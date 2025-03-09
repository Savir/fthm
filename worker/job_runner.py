import asyncio
import json
import os
import random

import redis
import structlog

from app.models import SyncTask
from tools import constants
from tools import util_redis
from tools.database import ctx_db
from tools.kafka import produce_message, consume_messages

log = structlog.get_logger()
# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", default="redis://redis:6379")
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

# Kafka Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", default="kafka:9092")


async def update_task_status(task_id: int, status: str):
    """Publishes task status update to Redis Pub/Sub."""
    try:
        task_id = int(task_id)
    except (ValueError, TypeError):
        log.exception("Invalid task id", task_id=task_id)
        raise
    if not status:
        raise ValueError(f"status can't be empty (when updating task_id={task_id}")

    # Update redis cache ASAP
    cache_key = util_redis.task_status_key(task_id)
    redis_client.set(cache_key, status, ex=3_600)

    # Update the value in the database:
    with ctx_db() as db:
        db.query(SyncTask).filter(SyncTask.id == task_id).update({SyncTask.status: status})
        db.commit()

    # Now, push a Kafka message in the 'status_updates' topic for anyone who
    # wants to listen for changes (namely, the backend and its websockets)
    message = json.dumps({"task_id": task_id, "status": status})
    log.info(
        "Pushing task status change",
        task_id=task_id,
        new_status=status,
        topic=constants.status_updates_topic,
    )
    await produce_message(constants.status_updates_topic, message)


async def _simulate_work(kafka_msg, *, job_name: str):
    task_data = json.loads(kafka_msg)
    log.info(f"Got message from Kafka topic '{job_name}'", task_data=task_data)
    task_id = task_data["task_id"]
    await update_task_status(task_id, job_name)
    try:
        # Pretend to take some time:
        await asyncio.sleep(2)
        if random.randint(0, 10) == 0:
            raise Exception(f"boooooOOOOOOm in {job_name}!!!")
    except Exception:
        log.exception(f"Exception occurred in job {job_name}", task_id=task_id)
        await update_task_status(task_id, constants.failed_status)
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
        await update_task_status(task_data["task_id"], constants.completed_status)


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
    except Exception:
        log.exception("Exception occurred in main()")
        loop.close()
        raise
    finally:
        loop.close()
