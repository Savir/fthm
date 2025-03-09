import asyncio
import json
import random

import structlog

from app.models import SyncTask
from tools import constants
from tools import util_redis
from tools.database import ctx_db
from tools.kafka import produce_message, consume_messages

log = structlog.get_logger()


async def update_task_status(task_id: int, status: str):
    """Does all the things when a task status is updated:
    - Set/update the Redis cache entry
    - Update the Database row
    - Publish the status via kafka for whomever wants to listen
    """
    try:
        task_id = int(task_id)
    except (ValueError, TypeError):
        log.exception("Invalid task id", task_id=task_id)
        raise
    if not status:
        raise ValueError(f"status can't be empty (when updating task_id={task_id}")

    # Update redis cache ASAP. This can potentially lower DB accesses
    redis_client = util_redis.get_client()
    cache_key = util_redis.task_status_key(task_id)
    redis_client.set(cache_key, status, ex=60 * 60 * 5)

    # Update the value in the database:
    with ctx_db() as db:
        db.query(SyncTask).filter(SyncTask.id == task_id).update({SyncTask.status: status})
        db.commit()

    # Now, push a Kafka message in the 'status_updates' topic to let the world know that
    # the status has changed
    message = json.dumps({"task_id": task_id, "status": status})
    log.info(
        "Pushing task status change",
        task_id=task_id,
        new_status=status,
        topic=constants.status_updates_topic,
    )
    await produce_message(constants.status_updates_topic, message)


async def _simulate_work(task_data, *, job_name: str):
    log.info(f"Got message from Kafka topic '{job_name}'", task_data=task_data)
    task_id = task_data["task_id"]
    await update_task_status(task_id, job_name)
    # Pretend to take some time:
    await asyncio.sleep(2)
    if random.randint(0, 10) == 0:
        raise Exception(f"boooooOOOOOOm in {job_name}!!!")


async def process_jobA():
    """Kafka consumer for JobA."""
    async for message in consume_messages(constants.start_topic):
        task_data = json.loads(message)
        task_id = task_data["task_id"]
        try:
            await _simulate_work(task_data, job_name="jobA")
        except Exception:
            log.exception("Exception while processing jobA", task_id=task_id)
            await update_task_status(task_id, constants.failed_status)
        else:
            await produce_message("jobB", message)


async def process_jobB():
    """Kafka consumer for JobB."""
    async for message in consume_messages("jobB"):
        task_data = json.loads(message)
        task_id = task_data["task_id"]
        try:
            await _simulate_work(task_data, job_name="jobB")
        except Exception:
            log.exception("Exception while processing jobB", task_id=task_id)
            await update_task_status(task_id, constants.failed_status)
        else:
            await produce_message("jobC", message)


async def process_jobC():
    """Kafka consumer for JobC."""
    async for message in consume_messages("jobC"):
        task_data = json.loads(message)
        task_id = task_data["task_id"]
        try:
            await _simulate_work(task_data, job_name="jobC")
        except Exception:
            log.exception("Exception while processing jobC", task_id=task_id)
            await update_task_status(task_id, constants.failed_status)
        else:
            # Mark completed
            await update_task_status(task_id, constants.completed_status)


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
