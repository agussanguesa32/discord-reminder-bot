from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional


VALID_REPEAT_TYPES = {"none", "daily", "weekly", "monthly", "yearly", "interval"}
VALID_REPEAT_UNITS = {"minutes", "hours", "days", "weeks", "months"}


class ReminderCreate(BaseModel):
    title: str
    description: Optional[str] = None
    next_run: datetime
    repeat_type: str = "none"
    repeat_interval: int = 0
    repeat_unit: Optional[str] = None
    repeat_days: Optional[str] = None
    advance_notice: int = 0
    timezone: str = "America/Argentina/Buenos_Aires"

    @field_validator("repeat_type")
    @classmethod
    def validate_repeat_type(cls, v: str) -> str:
        if v not in VALID_REPEAT_TYPES:
            raise ValueError(f"repeat_type debe ser uno de: {VALID_REPEAT_TYPES}")
        return v

    @field_validator("repeat_unit")
    @classmethod
    def validate_repeat_unit(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_REPEAT_UNITS:
            raise ValueError(f"repeat_unit debe ser uno de: {VALID_REPEAT_UNITS}")
        return v


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    next_run: Optional[datetime] = None
    repeat_type: Optional[str] = None
    repeat_interval: Optional[int] = None
    repeat_unit: Optional[str] = None
    repeat_days: Optional[str] = None
    advance_notice: Optional[int] = None
    timezone: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("repeat_type")
    @classmethod
    def validate_repeat_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_REPEAT_TYPES:
            raise ValueError(f"repeat_type debe ser uno de: {VALID_REPEAT_TYPES}")
        return v


class ReminderResponse(BaseModel):
    id: int
    user_id: str
    title: str
    description: Optional[str]
    next_run: str
    repeat_type: str
    repeat_interval: int
    repeat_unit: Optional[str]
    repeat_days: Optional[str]
    advance_notice: int
    timezone: str
    active: bool
    created_at: str

    @classmethod
    def from_row(cls, row) -> "ReminderResponse":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            next_run=row["next_run"],
            repeat_type=row["repeat_type"],
            repeat_interval=row["repeat_interval"] or 0,
            repeat_unit=row["repeat_unit"],
            repeat_days=row["repeat_days"],
            advance_notice=row["advance_notice"] or 0,
            timezone=row["timezone"],
            active=bool(row["active"]),
            created_at=row["created_at"],
        )


class TimezoneUpdate(BaseModel):
    timezone: str


class UserResponse(BaseModel):
    discord_user_id: str
    username: str
    avatar: Optional[str]
    timezone: str
