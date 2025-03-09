import os

import structlog
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

log = structlog.get_logger()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", default="kafka:9092")


async def produce_message(topic: str, message: str):
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
    await producer.start()
    try:
        await producer.send_and_wait(topic, message.encode("utf-8"))
        await producer.flush()
        log.info(f"Produced Kafka message", topic=topic, message=message)
    except Exception:
        log.exception("Error producing Kafka message", topic=topic, message=message)
        raise
    finally:
        await producer.stop()


async def consume_messages(topic, only_once=True):
    """Async generator that yields Kafka messages."""
    group_id = "sync_group"
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKER,
        group_id=group_id,
        enable_auto_commit=False if only_once else True,
    )
    await consumer.start()
    log.info("Starting consumer", topic=topic, group_id=group_id)
    value = None
    try:
        async for message in consumer:
            value = message.value.decode("utf-8")
            log.info("Consumed message from Kafka", topic=topic, value=value)
            if only_once:
                await consumer.commit()
            yield value
    except Exception:
        log.exception("Error consuming message from Kafka", topic=topic, value=value)
        raise
    finally:
        await consumer.stop()
