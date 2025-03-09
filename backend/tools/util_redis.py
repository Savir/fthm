import os

import redis

_redis_client = None


def get_client():
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", default="redis://redis:6379")
        _redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)
    return _redis_client


def task_status_key(task_id: int | str) -> str:
    return f"task-status_{task_id}"
