from datetime import datetime
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


def format_repeat(reminder) -> str:
    rt = reminder["repeat_type"]
    if rt == "none":
        return "No repeat"
    if rt == "daily":
        return "Daily"
    if rt == "weekly":
        days = reminder["repeat_days"] or ""
        day_list = [DAY_LABELS.get(d.strip(), d) for d in days.split(",") if d.strip()]
        return "Weekly · " + ", ".join(day_list)
    if rt == "interval":
        unit = UNIT_LABELS.get(reminder["repeat_unit"], reminder["repeat_unit"])
        return f"Every {reminder['repeat_interval']} {unit}"
    return rt


def format_next_run(reminder) -> str:
    tz = pytz.timezone(reminder["timezone"])
    dt = datetime.fromisoformat(reminder["next_run"]).replace(tzinfo=pytz.utc)
    local = dt.astimezone(tz)
    return local.strftime("%m/%d/%Y %H:%M")


def parse_datetime_with_tz(text: str, timezone: str) -> datetime | None:
    """Parse date strings like '06/25/2025 14:30' or '25/06/2025 14:30' in the user's timezone."""
    tz = pytz.timezone(timezone)
    formats = [
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%m/%d/%y %H:%M",
        "%d/%m/%y %H:%M",
        "%m/%d %H:%M",
        "%d/%m %H:%M",
    ]
    now = datetime.now(tz)
    for fmt in formats:
        try:
            dt = datetime.strptime(text.strip(), fmt)
            if "%Y" not in fmt and "%y" not in fmt:
                dt = dt.replace(year=now.year)
            local = tz.localize(dt)
            return local.astimezone(pytz.utc)
        except ValueError:
            continue
    return None


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
