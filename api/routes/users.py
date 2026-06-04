import pytz
from fastapi import APIRouter, HTTPException, Depends
from api.auth import get_current_user
from api.models import TimezoneUpdate, UserResponse
from shared import database as db

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(get_current_user)):
    tz = db.get_user_timezone(user["discord_user_id"])
    return UserResponse(
        discord_user_id=user["discord_user_id"],
        username=user["username"],
        avatar=user.get("avatar"),
        timezone=tz,
    )


@router.patch("/me/timezone")
def update_timezone(body: TimezoneUpdate, user: dict = Depends(get_current_user)):
    try:
        pytz.timezone(body.timezone)
    except pytz.UnknownTimeZoneError:
        raise HTTPException(status_code=400, detail=f"Timezone desconocido: {body.timezone}")
    db.set_user_timezone(user["discord_user_id"], body.timezone)
    return {"timezone": body.timezone}
