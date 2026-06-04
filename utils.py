import re
from datetime import datetime, timedelta
import pytz

REPEAT_LABELS = {
    "none": "No repeat",
    "daily": "Daily",
    "weekly": "Weekly",
    "interval": "Custom interval",
}

UNIT_LABELS = {
    "minutes": "minutes",
    "hours": "hours",
    "days": "days",
    "weeks": "weeks",
    "months": "months",
}

DAY_LABELS = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
}

DEFAULT_TZ = "America/Argentina/Buenos_Aires"


def parse_date(text: str, timezone: str) -> datetime | None:
    """
    Parse a date-only string (DD/MM/YYYY or DD/MM) in the user's timezone.
    Returns a timezone-aware UTC datetime at 00:00, or None on failure.
    The time component is filled in separately via the time picker.
    """
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    formats = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d/%m",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text.strip(), fmt)
            if "%Y" not in fmt and "%y" not in fmt:
                dt = dt.replace(year=now.year)
            return tz.localize(dt.replace(hour=0, minute=0, second=0, microsecond=0))
        except ValueError:
            continue
    return None


def build_datetime(date_local: datetime, hour: int, minute: int) -> datetime:
    """Combine a date (timezone-aware local) with hour and minute, return UTC."""
    combined = date_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return combined.astimezone(pytz.utc)


def preset_dt(timezone: str, days_ahead: int, hour: int, minute: int) -> datetime:
    """Return a UTC datetime for N days from today at HH:MM in the user's timezone."""
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    target = (now + timedelta(days=days_ahead)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    # If target ended up in the past (e.g. "tonight 8pm" but it's already 9pm), push a day forward
    if target <= now:
        target += timedelta(days=1)
    return target.astimezone(pytz.utc)


def discord_ts(dt: datetime, style: str = "f") -> str:
    """
    Return a Discord timestamp tag that renders natively in the client.
    f → June 25, 2025 5:00 PM  (absolute)
    R → in 2 hours              (relative, auto-updates)
    """
    return f"<t:{int(dt.timestamp())}:{style}>"


def parse_advance_notice(text: str) -> int | None:
    """
    Parse advance notice input and return total minutes, or None if invalid.

    Accepted formats:
      0            → 0 (disabled)
      30  / 30m    → 30 minutes
      2h  / 2hr    → 120 minutes
      1d  / 1day   → 1440 minutes
    """
    text = text.strip().lower()
    if not text or text == "0":
        return 0
    match = re.fullmatch(r"(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|day|days?)?", text)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2) or "m"
    if value <= 0:
        return 0
    if unit.startswith("d"):
        return value * 1440
    if unit.startswith("h"):
        return value * 60
    return value  # minutes


def format_advance_notice(minutes: int) -> str:
    """Return a human-readable advance notice string."""
    if not minutes:
        return "None"
    if minutes % 1440 == 0:
        n = minutes // 1440
        return f"{n} day{'s' if n != 1 else ''} before"
    if minutes % 60 == 0:
        n = minutes // 60
        return f"{n} hour{'s' if n != 1 else ''} before"
    return f"{minutes} min before"


def format_repeat(reminder) -> str:
    rt = reminder["repeat_type"]
    if rt == "none":
        return "One time"
    if rt == "daily":
        return "Daily"
    if rt == "weekly":
        days = reminder["repeat_days"] or ""
        day_list = [DAY_LABELS.get(d.strip(), d) for d in days.split(",") if d.strip()]
        return "Weekly · " + ", ".join(day_list)
    if rt == "monthly":
        return "Monthly"
    if rt == "yearly":
        return "Yearly"
    if rt == "interval":
        unit = UNIT_LABELS.get(reminder["repeat_unit"], reminder["repeat_unit"])
        return f"Every {reminder['repeat_interval']} {unit}"
    return rt


def format_next_run(reminder) -> str:
    """Plain-text DD/MM/YYYY HH:MM — used in select option descriptions."""
    tz = pytz.timezone(reminder["timezone"])
    dt = datetime.fromisoformat(reminder["next_run"]).replace(tzinfo=pytz.utc)
    return dt.astimezone(tz).strftime("%d/%m/%Y %H:%M")


def next_run_utc(reminder) -> datetime:
    return datetime.fromisoformat(reminder["next_run"]).replace(tzinfo=pytz.utc)


COMMON_TIMEZONES = [
    "America/Argentina/Buenos_Aires",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Sao_Paulo",
    "America/Santiago",
    "America/Bogota",
    "America/Lima",
    "America/Mexico_City",
    "Europe/London",
    "Europe/Madrid",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Rome",
    "UTC",
]
