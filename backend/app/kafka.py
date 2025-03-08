from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import os

KAFKA_BROKER = os.getenv('KAFKA_BROKER', default="kafka:9092")


async def produce_message(topic, message):
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
    await producer.start()
    try:
        await producer.send_and_wait(topic, message.encode("utf-8"))
        await producer.flush()
    finally:
        await producer.stop()


async def consume_messages(topic):
    consumer = AIOKafkaConsumer(topic, bootstrap_servers=KAFKA_BROKER, group_id="sync_group")
    await consumer.start()
    try:
        async for msg in consumer:
            print(f"Consumed message: {msg.value.decode('utf-8')}")
    finally:
        await consumer.stop()
