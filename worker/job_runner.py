import asyncio
import json
import os
import time

import redis
import structlog
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from tools import constants

log = structlog.get_logger()
# Redis Configuration
REDIS_URL = "redis://redis:6379"
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

# Kafka Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", default="kafka:9092")


async def produce_message(topic, message: bytes):
    """Send a message to a Kafka topic."""
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
    await producer.start()
    try:
        await producer.send_and_wait(topic, message)
        await producer.flush()  # Ensure messages are flushed immediately
    finally:
        await producer.stop()


def publish_task_status(task_id, status):
    """Publishes task status update to Redis Pub/Sub."""
    message = json.dumps({"task_id": task_id, "status": status})
    redis_client.set(str(task_id), status)
    redis_client.publish("task_updates", message)


def _simulate_work(kafka_msg, *, job_name: str):
    task_data = json.loads(kafka_msg.value.decode("utf-8"))
    log.info(f"Got message from Kafka topic '{job_name}'", task_data=task_data)
    task_id = task_data["task_id"]
    publish_task_status(task_id, job_name)

    # Process JobA (Simulated delay)
    time.sleep(2)


async def process_jobA():
    """Kafka consumer for JobA."""
    kafka_topic = constants.start_topic
    log.info(f"Starting processing messages in topic: {kafka_topic}")
    consumer = AIOKafkaConsumer(
        kafka_topic,
        bootstrap_servers=KAFKA_BROKER,
        group_id="sync_group",
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    log.info(" consumer started.")

    try:
        async for kafka_msg in consumer:
            _simulate_work(kafka_msg, job_name="jobA")
            await produce_message("jobB", kafka_msg.value)
    except Exception:
        log.exception("Got exception in jobA")
    finally:
        await consumer.stop()


async def process_jobB():
    """Kafka consumer for JobB."""
    consumer = AIOKafkaConsumer("jobB", bootstrap_servers=KAFKA_BROKER, group_id="sync_group")
    await consumer.start()
    try:
        async for kafka_msg in consumer:
            _simulate_work(kafka_msg, job_name="jobB")
            await produce_message("jobC", kafka_msg.value)
    finally:
        await consumer.stop()


async def process_jobC():
    """Kafka consumer for JobC."""
    consumer = AIOKafkaConsumer("jobC", bootstrap_servers=KAFKA_BROKER, group_id="sync_group")
    await consumer.start()
    try:
        async for kafka_msg in consumer:
            _simulate_work(kafka_msg, job_name="jobC")
            await produce_message("completed", kafka_msg.value)
    finally:
        await consumer.stop()


async def main():
    """Run job consumers concurrently."""
    await asyncio.gather(process_jobA(), process_jobB(), process_jobC())


if __name__ == "__main__":
    print("Starting processing Kafka messages.")
    asyncio.run(main())
