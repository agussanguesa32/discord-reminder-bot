import os
import logging
import httpx
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000/auth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7 days

DISCORD_OAUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_API_BASE = "https://discord.com/api/v10"


def create_access_token(user_data: dict) -> str:
    payload = {
        **user_data,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    return decode_token(credentials.credentials)


@router.get("/login")
def login():
    params = urlencode({
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
    })
    return RedirectResponse(f"{DISCORD_OAUTH_URL}?{params}")


@router.get("/callback")
async def callback(code: str):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            logger.error("Discord token exchange failed: %s %s", token_resp.status_code, token_resp.text)
            raise HTTPException(status_code=400, detail=f"Discord error: {token_resp.text}")

        discord_token = token_resp.json()["access_token"]

        user_resp = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {discord_token}"},
        )
        if user_resp.status_code != 200:
            logger.error("Discord user fetch failed: %s %s", user_resp.status_code, user_resp.text)
            raise HTTPException(status_code=400, detail="Error al obtener el usuario de Discord")

        discord_user = user_resp.json()

    jwt_token = create_access_token({
        "discord_user_id": discord_user["id"],
        "username": discord_user["username"],
        "avatar": discord_user.get("avatar"),
    })

    if FRONTEND_URL:
        return RedirectResponse(f"{FRONTEND_URL}/auth/callback?token={jwt_token}")

    return JSONResponse({"access_token": jwt_token, "token_type": "bearer"})


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
