import asyncio
import json
import os
import time

import redis
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import os
from app import constants

# Redis Configuration
REDIS_URL = "redis://redis:6379"
redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

# Kafka Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', default="kafka:9092")


async def produce_message(topic, message):
    """Send a message to a Kafka topic."""
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
    await producer.start()
    try:
        await producer.send_and_wait(topic, message.encode("utf-8"))
    finally:
        await producer.stop()


def publish_task_status(task_id, status):
    """Publishes task status update to Redis Pub/Sub."""
    message = json.dumps({"task_id": task_id, "status": status})
    redis_client.publish("task_updates", message)


def _simulate_work(kafka_msg, *, job_name: str):
    task_data = json.loads(kafka_msg.value.decode("utf-8"))
    task_id = task_data["task_id"]
    publish_task_status(task_id, job_name)

    # Process JobA (Simulated delay)
    time.sleep(2)


async def process_jobA():
    """Kafka consumer for JobA."""
    kafka_topic = constants.start_topic
    print(f"Starting processing messages in topic {kafka_topic}")
    consumer = AIOKafkaConsumer(kafka_topic, bootstrap_servers=KAFKA_BROKER, group_id="sync_group")
    await consumer.start()
    try:
        async for kafka_msg in consumer:
            print(f"Got message in Kafka topic '{kafka_topic}'")
            _simulate_work(kafka_msg, job_name="jobA")
            await produce_message("jobB", kafka_msg.value)
    except Exception as e:
        print("Exception in jobA", e)
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
    print("Starting processing Kafka messages")
    asyncio.run(main())
