import asyncio
import json
import logging
import os

import redis.asyncio as aioredis

import scheduler as sched

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CHANNEL = "reminder:events"
RETRY_DELAY = 5  # seconds between reconnection attempts


async def _handle(action: str, reminder_id: int) -> None:
    if action == "created":
        sched.schedule_new_reminder(reminder_id)
    elif action == "updated":
        sched.remove_reminder_jobs(reminder_id)
        sched.schedule_new_reminder(reminder_id)
    elif action == "deleted":
        sched.remove_reminder_jobs(reminder_id)
    else:
        logger.warning("Unknown Redis action: %s", action)


async def listen() -> None:
    """Background task: subscribe to Redis and react to reminder events.
    Reconnects automatically if the connection drops."""
    logger.info("Redis listener starting — channel: %s", CHANNEL)
    while True:
        client: aioredis.Redis | None = None
        try:
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.subscribe(CHANNEL)
            logger.info("Redis listener subscribed to %s", CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    action: str = data["action"]
                    rid: int = int(data["reminder_id"])
                    logger.info("Redis event received: %s reminder #%s", action, rid)
                    await _handle(action, rid)
                except Exception as e:
                    logger.error("Error handling Redis event %s: %s", message, e)

        except asyncio.CancelledError:
            logger.info("Redis listener cancelled — shutting down.")
            break
        except Exception as e:
            logger.error("Redis connection lost: %s — retrying in %ss", e, RETRY_DELAY)
            await asyncio.sleep(RETRY_DELAY)
        finally:
            if client:
                try:
                    await client.aclose()
                except Exception:
                    pass
