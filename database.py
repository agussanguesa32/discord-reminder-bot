import sqlite3
import os
import contextlib
from datetime import datetime, timezone as dt_timezone

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "reminders.db"))

DEFAULT_TZ = "America/Argentina/Buenos_Aires"


@contextlib.contextmanager
def _get_db():
    """Context manager that always closes the connection and rolls back on error."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL mode persists on the file — safe to set on every connection.
    # It prevents DB corruption if the process is killed mid-write.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                description TEXT,
                next_run    TEXT    NOT NULL,
                repeat_type TEXT    NOT NULL DEFAULT 'none',
                repeat_interval INTEGER      DEFAULT 0,
                repeat_unit TEXT             DEFAULT NULL,
                repeat_days TEXT             DEFAULT NULL,
                advance_notice INTEGER       DEFAULT 0,
                timezone    TEXT    NOT NULL DEFAULT 'America/Argentina/Buenos_Aires',
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id  TEXT PRIMARY KEY,
                timezone TEXT NOT NULL DEFAULT 'America/Argentina/Buenos_Aires'
            )
        """)
        conn.commit()


def get_user_timezone(user_id: str) -> str:
    with _get_db() as conn:
        row = conn.execute(
            "SELECT timezone FROM user_settings WHERE user_id = ?", (str(user_id),)
        ).fetchone()
    return row["timezone"] if row else DEFAULT_TZ


def set_user_timezone(user_id: str, tz_name: str):
    with _get_db() as conn:
        conn.execute(
            "INSERT INTO user_settings (user_id, timezone) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET timezone = excluded.timezone",
            (str(user_id), tz_name),
        )
        conn.commit()


def create_reminder(
    user_id: str,
    title: str,
    description: str,
    next_run: datetime,
    repeat_type: str,
    repeat_interval: int,
    repeat_unit: str,
    repeat_days: str,
    advance_notice: int,
    tz_name: str,
) -> int:
    with _get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders
                (user_id, title, description, next_run, repeat_type, repeat_interval,
                 repeat_unit, repeat_days, advance_notice, timezone, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                str(user_id),
                title,
                description,
                next_run.isoformat(),
                repeat_type,
                repeat_interval,
                repeat_unit,
                repeat_days,
                advance_notice,
                tz_name,
                datetime.now(dt_timezone.utc).isoformat(),
            ),
        )
        reminder_id = cursor.lastrowid
        conn.commit()
    return reminder_id


def get_reminder(reminder_id: int) -> sqlite3.Row | None:
    with _get_db() as conn:
        return conn.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        ).fetchone()


def get_user_reminders(user_id: str, active_only: bool = True) -> list:
    with _get_db() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE user_id = ? AND active = 1 ORDER BY next_run",
                (str(user_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE user_id = ? ORDER BY active DESC, next_run",
                (str(user_id),),
            ).fetchall()
    return rows


def get_all_active_reminders() -> list:
    with _get_db() as conn:
        return conn.execute(
            "SELECT * FROM reminders WHERE active = 1 ORDER BY next_run"
        ).fetchall()


def update_next_run(reminder_id: int, next_run: datetime):
    with _get_db() as conn:
        conn.execute(
            "UPDATE reminders SET next_run = ? WHERE id = ?",
            (next_run.isoformat(), reminder_id),
        )
        conn.commit()


def deactivate_reminder(reminder_id: int):
    with _get_db() as conn:
        conn.execute("UPDATE reminders SET active = 0 WHERE id = ?", (reminder_id,))
        conn.commit()


def delete_reminder(reminder_id: int, user_id: str) -> bool:
    with _get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, str(user_id)),
        )
        conn.commit()
    return cursor.rowcount > 0


def update_reminder_field(reminder_id: int, user_id: str, field: str, value) -> bool:
    allowed = {
        "title", "description", "next_run", "repeat_type", "repeat_interval",
        "repeat_unit", "repeat_days", "advance_notice", "timezone", "active",
    }
    if field not in allowed:
        raise ValueError(f"Field '{field}' is not allowed to be updated directly.")
    with _get_db() as conn:
        cursor = conn.execute(
            f"UPDATE reminders SET {field} = ? WHERE id = ? AND user_id = ?",
            (value, reminder_id, str(user_id)),
        )
        conn.commit()
    return cursor.rowcount > 0
