from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from api.auth import get_current_user
from api.models import ReminderCreate, ReminderUpdate, ReminderResponse
from shared import database as db

router = APIRouter()


@router.get("", response_model=list[ReminderResponse])
def list_reminders(active_only: bool = True, user: dict = Depends(get_current_user)):
    rows = db.get_user_reminders(user["discord_user_id"], active_only=active_only)
    return [ReminderResponse.from_row(r) for r in rows]


@router.post("", response_model=ReminderResponse, status_code=201)
def create_reminder(body: ReminderCreate, user: dict = Depends(get_current_user)):
    next_run = body.next_run
    if next_run.tzinfo is None:
        next_run = next_run.replace(tzinfo=timezone.utc)

    reminder_id = db.create_reminder(
        user_id=user["discord_user_id"],
        title=body.title,
        description=body.description or "",
        next_run=next_run,
        repeat_type=body.repeat_type,
        repeat_interval=body.repeat_interval,
        repeat_unit=body.repeat_unit,
        repeat_days=body.repeat_days,
        advance_notice=body.advance_notice,
        tz_name=body.timezone,
    )
    row = db.get_reminder(reminder_id)
    return ReminderResponse.from_row(row)


@router.get("/{reminder_id}", response_model=ReminderResponse)
def get_reminder(reminder_id: int, user: dict = Depends(get_current_user)):
    row = db.get_reminder(reminder_id)
    if not row or row["user_id"] != user["discord_user_id"]:
        raise HTTPException(status_code=404, detail="Reminder no encontrado")
    return ReminderResponse.from_row(row)


@router.patch("/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: int, body: ReminderUpdate, user: dict = Depends(get_current_user)
):
    row = db.get_reminder(reminder_id)
    if not row or row["user_id"] != user["discord_user_id"]:
        raise HTTPException(status_code=404, detail="Reminder no encontrado")

    updates = body.model_dump(exclude_none=True)
    for field, value in updates.items():
        if field == "next_run" and isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.isoformat()
        elif field == "active":
            value = 1 if value else 0
        db.update_reminder_field(reminder_id, user["discord_user_id"], field, value)

    return ReminderResponse.from_row(db.get_reminder(reminder_id))


@router.delete("/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: int, user: dict = Depends(get_current_user)):
    row = db.get_reminder(reminder_id)
    if not row or row["user_id"] != user["discord_user_id"]:
        raise HTTPException(status_code=404, detail="Reminder no encontrado")
    db.delete_reminder(reminder_id, user["discord_user_id"])
