import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.auth import router as auth_router
from api.routes.reminders import router as reminders_router
from api.routes.users import router as users_router
from api.redis_client import init_redis, close_redis
from shared import database as db

load_dotenv()

_REQUIRED_VARS = ["DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "JWT_SECRET"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Variables de entorno faltantes: {', '.join(missing)}")
    db.init_db()
    try:
        await init_redis()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Redis unavailable at startup — events won't be published: %s", e
        )
    yield
    await close_redis()


app = FastAPI(
    title="Reminder Bot API",
    description="API REST para gestionar recordatorios con autenticación Discord OAuth2",
    version="1.0.0",
    lifespan=lifespan,
)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(reminders_router, prefix="/api/reminders", tags=["reminders"])
app.include_router(users_router, prefix="/api/users", tags=["users"])


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
