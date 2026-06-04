import os
import json
import logging
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CHANNEL = "reminder:events"

_redis: aioredis.Redis | None = None


async def _connect() -> bool:
    """Try to create a fresh Redis connection. Returns True on success."""
    global _redis
    try:
        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        _redis = client
        logger.info("Redis connected: %s", REDIS_URL)
        return True
    except Exception as e:
        _redis = None
        logger.warning("Redis connection failed: %s", e)
        return False


async def init_redis() -> None:
    if not await _connect():
        raise ConnectionError(f"Cannot reach Redis at {REDIS_URL}")


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed.")


async def publish(action: str, reminder_id: int) -> None:
    global _redis

    # Attempt reconnect if the client is missing or stale
    if _redis is None:
        await _connect()

    if _redis is None:
        logger.warning("Redis unavailable — skipping publish %s #%s", action, reminder_id)
        return

    try:
        payload = json.dumps({"action": action, "reminder_id": reminder_id})
        await _redis.publish(CHANNEL, payload)
        logger.debug("Redis publish: %s", payload)
    except Exception as e:
        logger.error("Redis publish failed (%s #%s): %s — resetting connection", action, reminder_id, e)
        # Reset so the next publish attempt triggers a fresh reconnect
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None
