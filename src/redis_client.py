import os

import redis

REDIS_HOST = os.getenv("COC_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("COC_REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("COC_REDIS_DB", "0"))

redis_cache = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
    socket_timeout=None
)
