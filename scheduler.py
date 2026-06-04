import logging
from datetime import datetime, timedelta

import discord
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

import database as db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

_bot_ref = None


def set_bot(bot):
    global _bot_ref
    _bot_ref = bot


def _compute_next_run(reminder, from_dt: datetime) -> datetime | None:
    repeat_type = reminder["repeat_type"]
    if repeat_type == "none":
        return None

    tz = pytz.timezone(reminder["timezone"])
    local_from = from_dt.astimezone(tz)

    # Preserve the original scheduled time-of-day for daily/weekly so there
    # is no drift even when a missed reminder fires late on recovery.
    original_utc = datetime.fromisoformat(reminder["next_run"]).replace(tzinfo=pytz.utc)
    original_local = original_utc.astimezone(tz)
    orig_hour, orig_minute = original_local.hour, original_local.minute

    if repeat_type == "interval":
        unit = reminder["repeat_unit"]
        interval = reminder["repeat_interval"]
        if unit == "minutes":
            delta = timedelta(minutes=interval)
        elif unit == "hours":
            delta = timedelta(hours=interval)
        elif unit == "days":
            delta = timedelta(days=interval)
        elif unit == "weeks":
            delta = timedelta(weeks=interval)
        elif unit == "months":
            delta = timedelta(days=30 * interval)
        else:
            logger.error("Unknown repeat unit '%s' for reminder #%s", unit, reminder["id"])
            return None
        return from_dt + delta

    if repeat_type == "weekly":
        days_str = reminder["repeat_days"] or ""
        day_names = [d.strip().lower() for d in days_str.split(",") if d.strip()]
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        target_weekdays = sorted([day_map[d] for d in day_names if d in day_map])
        if not target_weekdays:
            logger.error("No valid weekdays for weekly reminder #%s", reminder["id"])
            return None

        current_weekday = local_from.weekday()
        best_diff = None
        for wd in target_weekdays:
            diff = (wd - current_weekday) % 7
            if diff == 0:
                diff = 7  # today already fired, skip to next week
            if best_diff is None or diff < best_diff:
                best_diff = diff

        candidate = local_from + timedelta(days=best_diff)
        candidate = candidate.replace(
            hour=orig_hour, minute=orig_minute, second=0, microsecond=0,
        )
        return candidate.astimezone(pytz.utc)

    if repeat_type == "daily":
        next_dt = local_from + timedelta(days=1)
        next_dt = next_dt.replace(
            hour=orig_hour, minute=orig_minute, second=0, microsecond=0,
        )
        return next_dt.astimezone(pytz.utc)

    logger.error("Unknown repeat_type '%s' for reminder #%s", repeat_type, reminder["id"])
    return None


async def _fire_reminder(reminder_id: int, is_advance: bool = False):
    try:
        reminder = db.get_reminder(reminder_id)
    except Exception as e:
        logger.error("DB error reading reminder #%s before fire: %s", reminder_id, e, exc_info=e)
        return

    if not reminder:
        logger.warning("Reminder #%s not found at fire time — skipping.", reminder_id)
        return
    if not reminder["active"]:
        logger.debug("Reminder #%s is inactive — skipping fire.", reminder_id)
        return

    bot = _bot_ref
    if not bot:
        logger.error("Bot reference is None when trying to fire reminder #%s", reminder_id)
        return

    try:
        user = await bot.fetch_user(int(reminder["user_id"]))
    except discord.NotFound:
        logger.error("User %s not found for reminder #%s — deactivating.", reminder["user_id"], reminder_id)
        try:
            db.deactivate_reminder(reminder_id)
        except Exception as e:
            logger.error("DB error deactivating reminder #%s after user not found: %s", reminder_id, e)
        return
    except discord.HTTPException as e:
        logger.error("HTTP error fetching user %s for reminder #%s: %s", reminder["user_id"], reminder_id, e)
        return

    tz = pytz.timezone(reminder["timezone"])
    next_run_utc = datetime.fromisoformat(reminder["next_run"]).replace(tzinfo=pytz.utc)
    next_run_local = next_run_utc.astimezone(tz)
    tz_label = reminder["timezone"].split("/")[-1].replace("_", " ")

    now_utc = datetime.now(pytz.utc)

    if is_advance:
        embed = discord.Embed(
            title=f"⏰ Upcoming reminder: {reminder['title']}",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="Scheduled for",
            value=next_run_local.strftime("%m/%d/%Y %H:%M"),
            inline=True,
        )
        embed.add_field(name="Timezone", value=tz_label, inline=True)
        if reminder["description"]:
            embed.add_field(name="Description", value=reminder["description"], inline=False)
        embed.set_footer(text=f"{reminder['advance_notice']} min advance notice · ID #{reminder_id}")
    else:
        missed = next_run_utc < now_utc - timedelta(seconds=30)
        embed = discord.Embed(
            title=f"🔔 {reminder['title']}",
            color=discord.Color.yellow() if missed else discord.Color.green(),
        )
        if missed:
            embed.description = "⚠️ This reminder was delivered late because the bot was offline."
        if reminder["description"]:
            embed.add_field(name="Description", value=reminder["description"], inline=False)
        embed.add_field(
            name="Scheduled for",
            value=next_run_local.strftime("%m/%d/%Y %H:%M"),
            inline=True,
        )
        embed.add_field(name="Timezone", value=tz_label, inline=True)
        embed.set_footer(text=f"ID #{reminder_id}")

    try:
        await user.send(embed=embed)
        logger.info(
            "Fired reminder #%s (%s) for user %s [advance=%s%s]",
            reminder_id,
            reminder["title"],
            reminder["user_id"],
            is_advance,
            ", missed=True" if not is_advance and missed else "",
        )
    except discord.Forbidden:
        logger.error(
            "Cannot DM user %s for reminder #%s — DMs may be disabled. Deactivating.",
            reminder["user_id"], reminder_id,
        )
        try:
            db.deactivate_reminder(reminder_id)
        except Exception as e:
            logger.error("DB error deactivating reminder #%s after Forbidden: %s", reminder_id, e)
        return
    except discord.HTTPException as e:
        logger.error("Failed to send DM for reminder #%s to user %s: %s", reminder_id, reminder["user_id"], e)
        return

    if not is_advance:
        try:
            now_utc = datetime.now(pytz.utc)  # recompute after async send
            next_run = _compute_next_run(reminder, now_utc)
            if next_run:
                db.update_next_run(reminder_id, next_run)
                _schedule_reminder_jobs(reminder_id)
                logger.info("Rescheduled reminder #%s → next run at %s UTC", reminder_id, next_run.isoformat())
            else:
                db.deactivate_reminder(reminder_id)
                logger.info("Reminder #%s completed (no repeat) — deactivated.", reminder_id)
        except Exception as e:
            logger.error("DB error rescheduling reminder #%s after fire: %s", reminder_id, e, exc_info=e)


def _schedule_reminder_jobs(reminder_id: int):
    reminder = db.get_reminder(reminder_id)
    if not reminder:
        logger.warning("_schedule_reminder_jobs: reminder #%s not found.", reminder_id)
        return
    if not reminder["active"]:
        logger.debug("_schedule_reminder_jobs: reminder #%s is inactive, skipping.", reminder_id)
        return

    now_utc = datetime.now(pytz.utc)
    next_run_utc = datetime.fromisoformat(reminder["next_run"]).replace(tzinfo=pytz.utc)

    main_job_id = f"reminder_{reminder_id}"
    advance_job_id = f"advance_{reminder_id}"

    for jid in (main_job_id, advance_job_id):
        if scheduler.get_job(jid):
            scheduler.remove_job(jid)

    if next_run_utc <= now_utc:
        # Missed while the bot was down — fire immediately with a small delay
        # so the bot has time to fully connect before sending the DM.
        fire_at = now_utc + timedelta(seconds=10)
        scheduler.add_job(
            _fire_reminder,
            trigger=DateTrigger(run_date=fire_at),
            id=main_job_id,
            args=[reminder_id, False],
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info("Reminder #%s was missed — scheduled for immediate recovery in 10s.", reminder_id)
        return

    scheduler.add_job(
        _fire_reminder,
        trigger=DateTrigger(run_date=next_run_utc),
        id=main_job_id,
        args=[reminder_id, False],
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.debug("Scheduled reminder #%s at %s UTC", reminder_id, next_run_utc.isoformat())

    advance = reminder["advance_notice"]
    if advance and advance > 0:
        advance_dt = next_run_utc - timedelta(minutes=advance)
        if advance_dt > now_utc:
            scheduler.add_job(
                _fire_reminder,
                trigger=DateTrigger(run_date=advance_dt),
                id=advance_job_id,
                args=[reminder_id, True],
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.debug(
                "Scheduled advance notice for reminder #%s at %s UTC (%s min before)",
                reminder_id, advance_dt.isoformat(), advance,
            )


def load_all_reminders():
    try:
        reminders = db.get_all_active_reminders()
    except Exception as e:
        logger.error("Failed to load reminders from database: %s", e, exc_info=e)
        return

    loaded = 0
    for r in reminders:
        try:
            _schedule_reminder_jobs(r["id"])
            loaded += 1
        except Exception as e:
            logger.error("Failed to schedule reminder #%s on startup: %s", r["id"], e, exc_info=e)

    logger.info("Loaded %d/%d active reminders into scheduler.", loaded, len(reminders))


def schedule_new_reminder(reminder_id: int):
    try:
        _schedule_reminder_jobs(reminder_id)
    except Exception as e:
        logger.error("Failed to schedule new reminder #%s: %s", reminder_id, e, exc_info=e)


def remove_reminder_jobs(reminder_id: int):
    removed = 0
    for jid in (f"reminder_{reminder_id}", f"advance_{reminder_id}"):
        if scheduler.get_job(jid):
            scheduler.remove_job(jid)
            removed += 1
    if removed:
        logger.debug("Removed %d job(s) for reminder #%s.", removed, reminder_id)
