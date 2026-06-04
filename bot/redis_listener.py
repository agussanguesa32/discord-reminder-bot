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
POLL_TIMEOUT = 5.0  # seconds to wait for a message before polling again


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
    Uses get_message() polling so idle connections never raise TimeoutError.
    Reconnects automatically if the connection actually drops."""
    logger.info("Redis listener starting — channel: %s", CHANNEL)
    while True:
        client: aioredis.Redis | None = None
        try:
            # socket_timeout=None: never time out waiting for pub/sub messages.
            # socket_keepalive=True: TCP keepalive to detect dead connections.
            client = aioredis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_timeout=None,
                socket_connect_timeout=10,
                socket_keepalive=True,
            )
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            await pubsub.subscribe(CHANNEL)
            logger.info("Redis listener subscribed to %s", CHANNEL)

            while True:
                # get_message returns None after POLL_TIMEOUT with no message.
                # It does NOT raise an exception on timeout — only on real errors.
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=POLL_TIMEOUT,
                )
                if message is None:
                    continue  # idle — keep polling

                if message.get("type") != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    action: str = data["action"]
                    rid: int = int(data["reminder_id"])
                    logger.info("Redis event: %s reminder #%s", action, rid)
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
