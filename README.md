# Reminder Bot

A personal Discord reminder bot with a REST API and web frontend. Reminders are delivered via Discord DMs and can be managed from either the Discord slash commands or the web interface.

---

## Table of Contents

- [Architecture](#architecture)
- [Features](#features)
- [Discord Bot Commands](#discord-bot-commands)
- [Web Frontend](#web-frontend)
- [REST API](#rest-api)
  - [Authentication](#authentication)
  - [Endpoints](#endpoints)
  - [Request & Response Examples](#request--response-examples)
- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Discord Application](#discord-application)
  - [Running with Docker (recommended)](#running-with-docker-recommended)
  - [Running locally](#running-locally)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Technical Notes](#technical-notes)

---

## Architecture

```
┌─────────────┐     slash commands     ┌─────────────────┐
│   Discord   │ ◄────────────────────► │   Bot (Python)  │
└─────────────┘                        └────────┬────────┘
                                                │ read/write
┌─────────────┐   OAuth2 + REST API    ┌────────▼────────┐
│  Frontend   │ ◄────────────────────► │   API (FastAPI) │
│  (Next.js)  │                        └────────┬────────┘
└─────────────┘                                 │ read/write
                                       ┌────────▼────────┐
                                       │  SQLite (shared) │
                                       └─────────────────┘
                    ┌─────────────────────────────────┐
                    │  Redis pub/sub (instant sync)    │
                    │  API publishes → Bot schedules   │
                    └─────────────────────────────────┘
```

**Four Docker services:** `redis`, `bot`, `api`, `frontend` — all orchestrated with Docker Compose. The bot and API share the same SQLite database via a bind-mounted volume. When a reminder is created or changed via the API or frontend, Redis delivers the event to the bot instantly so the job is scheduled without a restart.

---

## Features

- **Discord slash commands** — create, list, pause, resume, and delete reminders interactively
- **Web interface** — full CRUD via a Next.js frontend with Discord OAuth2 login
- **Repeat schedules** — once, daily, weekly (specific days), monthly, yearly, or every N minutes/hours/days/weeks
- **Advance notice** — optional early notification before the reminder fires
- **Missed reminders** — delivered automatically on bot restart with a late-delivery notice
- **Per-user timezone** — each user configures their own; defaults to `America/Argentina/Buenos_Aires`
- **Pause / Resume** — suspend a reminder without deleting it
- **Real-time sync** — reminders created via the web are scheduled instantly via Redis pub/sub, no bot restart needed
- **Resilient** — bot reconnects to Discord and Redis automatically; API degrades gracefully if Redis is unavailable

---

## Discord Bot Commands

| Command | Description |
|---|---|
| `/reminder` | Create a new reminder via interactive modal |
| `/reminders` | List all your active reminders |
| `/delete-reminder` | Delete a reminder |
| `/timezone` | View your current timezone |
| `/timezone zone:<tz>` | Change your timezone (e.g. `America/New_York`) |

---

## Web Frontend

Available at `http://<host>:3000` after startup.

**Login** — click "Continue with Discord" to authenticate via OAuth2. Your session is stored in an HttpOnly cookie (7-day expiry).

**Dashboard** — shows all your reminders with a live countdown. From here you can:
- Create reminders with a date picker, time selector, and quick presets ("Tonight 8pm", "Tomorrow 9am", etc.)
- Edit any field of an existing reminder
- Pause / resume reminders
- Delete reminders with a confirmation dialog

---

## REST API

The API runs on port `8000`. Interactive docs (Swagger UI) are at `http://<host>:8000/docs`.

All `/api/*` endpoints require a valid JWT in the `Authorization` header.

### Authentication

The API uses the **Discord OAuth2 Authorization Code** flow.

#### Flow

```
1. Browser → GET /auth/login  →  302 redirect to Discord
2. User grants permission on Discord
3. Discord → GET /auth/callback?code=...  →  API exchanges code for Discord token
4. API fetches Discord user profile, issues a signed JWT
5. If FRONTEND_URL is set: redirect to <FRONTEND_URL>/auth/callback?token=<jwt>
   Otherwise: return {"access_token": "<jwt>", "token_type": "bearer"}
6. Include JWT in all subsequent requests: Authorization: Bearer <jwt>
```

JWT tokens are signed with `HS256` and expire after **7 days**.

#### Endpoints

**Auth & health** (no token required):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/login` | Redirect to Discord OAuth2 |
| `GET` | `/auth/callback?code=...` | OAuth2 callback — issues JWT |
| `GET` | `/auth/me` | Decode and return current token payload |
| `GET` | `/health` | Health check — `{"status": "ok"}` |

**Reminders** (Bearer token required):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/reminders` | List reminders (`?active_only=true` by default) |
| `POST` | `/api/reminders` | Create a reminder |
| `GET` | `/api/reminders/{id}` | Get a single reminder |
| `PATCH` | `/api/reminders/{id}` | Update one or more fields |
| `DELETE` | `/api/reminders/{id}` | Delete a reminder |

**Users** (Bearer token required):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/users/me` | Get profile and timezone |
| `PATCH` | `/api/users/me/timezone` | Update your timezone |

---

### Request & Response Examples

#### List reminders

```http
GET /api/reminders
GET /api/reminders?active_only=false
Authorization: Bearer <token>
```

```json
[
  {
    "id": 1,
    "user_id": "123456789012345678",
    "title": "Doctor appointment",
    "description": "Bring insurance card",
    "next_run": "2026-06-10T17:00:00+00:00",
    "repeat_type": "none",
    "repeat_interval": 0,
    "repeat_unit": null,
    "repeat_days": null,
    "advance_notice": 30,
    "timezone": "America/Argentina/Buenos_Aires",
    "active": true,
    "created_at": "2026-06-04T12:00:00+00:00"
  }
]
```

#### Create a reminder

```http
POST /api/reminders
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "title": "Take medication",
  "description": "After breakfast",
  "next_run": "2026-06-05T08:00:00-03:00",
  "repeat_type": "daily",
  "advance_notice": 0,
  "timezone": "America/Argentina/Buenos_Aires"
}
```

`next_run` is any ISO 8601 datetime. Without a timezone offset, UTC is assumed.

**`repeat_type` values:**

| Value | Required extra fields | Description |
|---|---|---|
| `none` | — | One-time (default) |
| `daily` | — | Every day at the same time |
| `weekly` | `repeat_days` | Specific weekdays |
| `monthly` | — | Same day each month |
| `yearly` | — | Same date each year |
| `interval` | `repeat_interval`, `repeat_unit` | Every N units |

`repeat_days` — comma-separated: `"monday,tuesday,wednesday,thursday,friday"`

`repeat_unit` — one of: `minutes`, `hours`, `days`, `weeks`

**Weekly example:**
```json
{
  "title": "Team standup",
  "next_run": "2026-06-09T09:00:00-03:00",
  "repeat_type": "weekly",
  "repeat_days": "monday,tuesday,wednesday,thursday,friday",
  "timezone": "America/Argentina/Buenos_Aires"
}
```

**Custom interval example:**
```json
{
  "title": "Drink water",
  "next_run": "2026-06-04T10:00:00-03:00",
  "repeat_type": "interval",
  "repeat_interval": 2,
  "repeat_unit": "hours",
  "timezone": "America/Argentina/Buenos_Aires"
}
```

Response — `201 Created` — the full reminder object.

#### Update a reminder

Send only the fields you want to change:

```http
PATCH /api/reminders/1
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{ "title": "Updated title", "advance_notice": 15 }
```

Pause: `{ "active": false }` — Resume: `{ "active": true }`

Response — `200 OK` — the updated reminder object.

#### Delete a reminder

```http
DELETE /api/reminders/1
Authorization: Bearer <token>
```

Response — `204 No Content`

#### Get / update timezone

```http
GET /api/users/me
Authorization: Bearer <token>
```

```json
{
  "discord_user_id": "123456789012345678",
  "username": "yourname",
  "avatar": "abc123",
  "timezone": "America/Argentina/Buenos_Aires"
}
```

```http
PATCH /api/users/me/timezone
Authorization: Bearer <token>
Content-Type: application/json

{ "timezone": "America/New_York" }
```

Any valid [tz database name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) is accepted. Returns `400` for unknown values.

#### Error responses

```json
{ "detail": "Human-readable message" }
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request or OAuth failure |
| `401` | Missing, invalid, or expired JWT |
| `404` | Reminder not found or belongs to another user |
| `422` | Validation error — `detail` is an array with field-level info |

---

## Setup

### Prerequisites

- **Docker & Docker Compose** — for the recommended deployment
- **Python 3.12+** and **Node.js 22+** — only needed for local development without Docker
- A **Discord application** — [create one here](https://discord.com/developers/applications)

### Discord Application

You need one Discord application for both the bot token and the OAuth2 credentials.

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and create (or open) your app.
2. **Bot tab** → Reset Token → copy `DISCORD_TOKEN`.
3. **OAuth2 tab** → copy `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET`.
4. **OAuth2 → Redirects** → Add `http://<your-host>:8000/auth/callback` (must match `DISCORD_REDIRECT_URI` exactly).
5. **Bot tab** → enable **Message Content Intent** and **Server Members Intent** if required.

---

### Running with Docker (recommended)

```bash
git clone <repo-url>
cd reminder-bot

# Copy and fill in the environment file
cp .env.example .env
# Edit .env — at minimum set the six required variables (see below)

# Build and start all four services (redis, bot, api, frontend)
docker compose up --build -d

# Follow logs
docker compose logs -f

# Per-service logs
docker compose logs -f bot
docker compose logs -f api

# Stop everything
docker compose down
```

The SQLite database is stored in `./data/reminders.db` on the host and survives container rebuilds, restarts, and `docker compose down`.

**Ports exposed on the host:**

| Service | Port | URL |
|---|---|---|
| API | `8000` | `http://<host>:8000` · docs at `/docs` |
| Frontend | `3000` | `http://<host>:3000` |
| Redis | internal only | not exposed |

---

### Running locally

**All three Python services** share the same virtualenv at the project root:

```bash
python -m venv venv
source venv/bin/activate          # Linux/macOS
venv\Scripts\activate             # Windows PowerShell

pip install -r bot/requirements.txt -r api/requirements.txt
cp .env.example .env
# Fill in .env
```

**Start Redis** (required for real-time sync — skip if running bot only):

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Bot:**

```bash
PYTHONPATH=bot:. python bot/bot.py          # Linux/macOS
$env:PYTHONPATH="bot;."; python bot/bot.py  # Windows PowerShell
```

**API:**

```bash
PYTHONPATH=. uvicorn api.main:app --reload          # Linux/macOS
$env:PYTHONPATH="."; uvicorn api.main:app --reload  # Windows PowerShell
# Docs at http://localhost:8000/docs
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

The frontend reads the root `.env` automatically (via `next.config.ts`) — no separate `.env.local` needed.

---

## Environment Variables

All variables live in a single `.env` file at the project root. Copy `.env.example` as a starting point.

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ Bot | Discord bot token |
| `DISCORD_CLIENT_ID` | ✅ API | OAuth2 app client ID |
| `DISCORD_CLIENT_SECRET` | ✅ API | OAuth2 app client secret |
| `DISCORD_REDIRECT_URI` | ✅ API | Redirect URI registered in Discord portal. Must match exactly. |
| `JWT_SECRET` | ✅ API | Secret for signing JWTs. Generate: `openssl rand -hex 32` |
| `NEXT_PUBLIC_API_URL` | ✅ Frontend | Public API URL used by the browser for the Discord login redirect (e.g. `http://192.168.0.6:8000`) |
| `FRONTEND_URL` | ✅ API+Frontend | Public frontend URL. The API redirects here after OAuth. Also used by the frontend container to build absolute redirect URLs. |
| `REDIS_URL` | ❌ | Redis connection string. Docker overrides this to `redis://redis:6379`. Local default: `redis://localhost:6379` |
| `DB_PATH` | ❌ | SQLite file path. Docker sets this to `/app/data/reminders.db`. |

> **Local vs Docker URLs:** When running with Docker on a local network, set `NEXT_PUBLIC_API_URL` and `FRONTEND_URL` to the machine's LAN IP (e.g. `http://192.168.0.6:8000`). `REDIS_URL` is automatically set to the internal Docker service name and does not need to be in `.env` for Docker deployments.

---

## Project Structure

```
reminder-bot/
├── bot/                         # Discord bot service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── bot.py                   # Entry point, graceful shutdown, Redis listener task
│   ├── scheduler.py             # APScheduler jobs — fire, reschedule, recovery
│   ├── redis_listener.py        # Subscribes to Redis, schedules jobs on API events
│   ├── utils.py                 # Date parsing, formatting, timezone helpers
│   ├── cogs/
│   │   └── reminders.py         # Slash commands
│   └── views/
│       └── reminder_views.py    # Discord UI — modals, selects, buttons
│
├── api/                         # REST API service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                  # FastAPI app, CORS, lifespan (DB + Redis init)
│   ├── auth.py                  # Discord OAuth2 flow, JWT sign/verify
│   ├── models.py                # Pydantic request/response schemas
│   ├── redis_client.py          # Redis publisher with auto-reconnect
│   └── routes/
│       ├── reminders.py         # CRUD endpoints
│       └── users.py             # Profile and timezone endpoints
│
├── shared/
│   └── database.py              # SQLite layer — shared by bot and API
│
├── frontend/                    # Web UI (Next.js 16, shadcn/ui, Tailwind v4)
│   ├── Dockerfile
│   ├── next.config.ts           # Standalone output, loads root .env in dev
│   ├── proxy.ts                 # Route protection (Next.js 16 — replaces middleware.ts)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Login page
│   │   ├── dashboard/
│   │   │   └── page.tsx         # Reminder list (Server Component)
│   │   ├── auth/callback/
│   │   │   └── route.ts         # Receives JWT from API, sets HttpOnly cookie
│   │   ├── api/auth/logout/
│   │   │   └── route.ts         # Clears session cookie
│   │   └── actions.ts           # Server Actions (create, update, delete, toggle)
│   ├── components/
│   │   ├── reminders-shell.tsx  # Dashboard client shell, dialog state
│   │   ├── reminder-card.tsx    # Single reminder card with actions
│   │   ├── reminder-form.tsx    # Create/edit form — two-column layout
│   │   ├── countdown.tsx        # Live countdown timer
│   │   └── logout-button.tsx
│   └── lib/
│       ├── api.ts               # Typed API client (server-side, uses API_URL)
│       └── session.ts           # HttpOnly cookie helpers (server-only)
│
├── data/                        # SQLite volume (gitignored)
├── docker-compose.yml           # redis, bot, api, frontend
├── .env.example
└── .gitignore
```

---

## Technical Notes

**Real-time sync via Redis pub/sub** — When a reminder is created, updated, or deleted through the API, a message is published to the `reminder:events` Redis channel. The bot subscribes to that channel and immediately schedules or cancels the corresponding APScheduler job. If Redis is unavailable, the API logs a warning but continues operating; the bot reconnects automatically with a 5-second retry loop.

**SQLite shared between services** — Both the bot and API access the same SQLite file via a bind-mounted Docker volume. SQLite is configured with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` on every connection, which allows concurrent reads and protects against corruption if a process is killed mid-write. Field updates are applied atomically in a single transaction.

**Session security** — JWTs are stored in `HttpOnly` cookies set server-side by Next.js. Client-side JavaScript never touches the token. The `Secure` flag is enabled automatically when `FRONTEND_URL` starts with `https://`.

**Graceful shutdown** — The bot handles `SIGTERM` (sent by Docker on `docker stop`) and `SIGINT` (Ctrl-C). It cancels the Redis listener task, stops APScheduler, and closes the Discord connection cleanly before the process exits.

**Missed reminders** — On startup the bot loads all active reminders from the database and reschedules them. Any reminder whose `next_run` is in the past fires within 10 seconds with a "delivered late" notice. Repeating reminders continue from the original schedule without drift.

**Repeat drift prevention** — Daily and weekly reminders always preserve the original time-of-day, even after a missed fire or recovery. Monthly reminders clamp to the last valid day when the scheduled day doesn't exist in the target month (e.g. 31st → February).

**Next.js 16 breaking change** — `middleware.ts` was renamed to `proxy.ts` in Next.js 16 and the exported function changed from `middleware` to `proxy`. The `proxy.ts` at the project root protects `/dashboard` and redirects unauthenticated requests to the login page.

**PYTHONPATH** — The bot Dockerfile sets `PYTHONPATH=/app/bot:/app`, allowing `import scheduler` (from `bot/`) and `from shared import database` (from the project root) to work without package installation. The API Dockerfile sets `PYTHONPATH=/app` for the same reason.
