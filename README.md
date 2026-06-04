# Reminder Bot

A personal Discord reminder bot that communicates exclusively via **Direct Messages**, paired with a **REST API** for programmatic access and future frontend integration.

---

## Table of Contents

- [Bot Features](#bot-features)
- [Bot Commands](#bot-commands)
- [REST API](#rest-api)
  - [Authentication](#authentication)
  - [Endpoints](#endpoints)
  - [Request & Response Examples](#request--response-examples)
- [Setup](#setup)
  - [Running locally](#running-locally)
  - [Running with Docker](#running-with-docker)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Technical Notes](#technical-notes)

---

## Bot Features

- **Create reminders** via an interactive modal — title, description, date/time, and advance notice
- **Repeat options** — no repeat, daily, weekly (pick specific days), or a fully custom interval (every N minutes / hours / days / weeks / months)
- **Advance notice** — get notified X minutes before the reminder fires
- **Persistent** — all reminders survive bot restarts; missed ones are delivered automatically on next startup
- **Per-user timezone** — defaults to `America/Argentina/Buenos_Aires`, configurable per user
- **Pause / Resume / Delete** reminders without recreating them

---

## Bot Commands

| Command | Description |
|---|---|
| `/reminder` | Create a new reminder |
| `/reminders` | List all your active reminders |
| `/delete-reminder` | Delete a reminder |
| `/timezone` | View your current timezone |
| `/timezone zone:<tz>` | Change your timezone (e.g. `America/New_York`) |

---

## REST API

The API runs on port `8000` and uses **Discord OAuth2** to authenticate users. All protected endpoints require a JWT bearer token obtained via the OAuth2 flow.

Interactive docs (Swagger UI) are available at `http://localhost:8000/docs` once the API is running.

### Authentication

The API uses the **Authorization Code** OAuth2 flow with Discord.

#### Flow

```
1. Frontend redirects user to GET /auth/login
2. User logs in on Discord and grants permission
3. Discord redirects to /auth/callback?code=...
4. API exchanges the code for a Discord access token
5. API fetches the user's Discord profile
6. API returns a signed JWT (7-day expiry)
7. Frontend stores the JWT and sends it as Bearer token on every request
```

#### Getting a token

**Step 1 — Redirect the user to Discord login:**

```
GET /auth/login
```

This returns a redirect to Discord's OAuth2 authorization page. No parameters needed.

**Step 2 — Handle the callback:**

Discord redirects back to your configured `DISCORD_REDIRECT_URI` with a `code` query parameter. The API handles this automatically:

```
GET /auth/callback?code=<discord_code>
```

Response (when `FRONTEND_URL` is not set):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

When `FRONTEND_URL` is configured, the API redirects to:
```
http://your-frontend.com?token=eyJhbGci...
```

**Step 3 — Use the token:**

Include the JWT in the `Authorization` header on all subsequent requests:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Verify your token

```
GET /auth/me
Authorization: Bearer <token>
```

```json
{
  "discord_user_id": "123456789012345678",
  "username": "yourname",
  "avatar": "abc123def456"
}
```

---

### Endpoints

All `/api/*` endpoints require `Authorization: Bearer <token>`.

#### Reminders

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/reminders` | List your reminders |
| `POST` | `/api/reminders` | Create a reminder |
| `GET` | `/api/reminders/{id}` | Get a single reminder |
| `PATCH` | `/api/reminders/{id}` | Update reminder fields |
| `DELETE` | `/api/reminders/{id}` | Delete a reminder |

#### Users

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/users/me` | Get your profile and timezone |
| `PATCH` | `/api/users/me/timezone` | Update your timezone |

#### Auth & Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/login` | Redirect to Discord OAuth2 |
| `GET` | `/auth/callback` | OAuth2 callback — returns JWT |
| `GET` | `/auth/me` | Verify token and get user info |
| `GET` | `/health` | Health check |

---

### Request & Response Examples

#### List reminders

```
GET /api/reminders
GET /api/reminders?active_only=false    # include inactive/past reminders
Authorization: Bearer <token>
```

```json
[
  {
    "id": 1,
    "user_id": "123456789012345678",
    "title": "Doctor appointment",
    "description": "Bring insurance card",
    "next_run": "2026-06-10T14:00:00+00:00",
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

---

#### Create a reminder

```
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

`next_run` accepts any ISO 8601 datetime. If no timezone offset is provided, UTC is assumed.

**`repeat_type` values:**

| Value | Description |
|-------|-------------|
| `none` | One-time reminder (default) |
| `daily` | Every day at the same time |
| `weekly` | Specific weekdays — set `repeat_days` |
| `monthly` | Every month on the same day |
| `yearly` | Every year on the same date |
| `interval` | Every N units — set `repeat_interval` and `repeat_unit` |

**`repeat_unit` values** (only for `interval`): `minutes`, `hours`, `days`, `weeks`, `months`

**`repeat_days`** (only for `weekly`): comma-separated list of day names, e.g. `"monday,wednesday,friday"`

**Weekly reminder example:**

```json
{
  "title": "Team standup",
  "next_run": "2026-06-09T09:00:00-03:00",
  "repeat_type": "weekly",
  "repeat_days": "monday,tuesday,wednesday,thursday,friday",
  "timezone": "America/Argentina/Buenos_Aires"
}
```

**Interval reminder example:**

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

Response `201 Created`:

```json
{
  "id": 5,
  "user_id": "123456789012345678",
  "title": "Take medication",
  ...
}
```

---

#### Get a single reminder

```
GET /api/reminders/5
Authorization: Bearer <token>
```

Returns the same shape as a single item in the list. Returns `404` if the reminder doesn't exist or belongs to another user.

---

#### Update a reminder

Only include the fields you want to change. All fields are optional.

```
PATCH /api/reminders/5
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "title": "Take medication (updated)",
  "advance_notice": 15
}
```

**Pause a reminder:**

```json
{ "active": false }
```

**Resume a reminder:**

```json
{ "active": true }
```

**Change the scheduled time:**

```json
{ "next_run": "2026-06-06T09:00:00-03:00" }
```

Response: the updated reminder object.

---

#### Delete a reminder

```
DELETE /api/reminders/5
Authorization: Bearer <token>
```

Response: `204 No Content`

---

#### Get your profile

```
GET /api/users/me
Authorization: Bearer <token>
```

```json
{
  "discord_user_id": "123456789012345678",
  "username": "yourname",
  "avatar": "abc123def456",
  "timezone": "America/Argentina/Buenos_Aires"
}
```

---

#### Update your timezone

```
PATCH /api/users/me/timezone
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{ "timezone": "America/New_York" }
```

```json
{ "timezone": "America/New_York" }
```

Any valid [tz database name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) is accepted. Returns `400` for unknown values.

---

#### Error responses

All errors follow this shape:

```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request — invalid input or OAuth error |
| `401` | Missing or invalid/expired JWT |
| `404` | Reminder not found or belongs to another user |
| `422` | Validation error — check the `detail` array for field-level errors |

---

## Setup

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for the full stack)
- A Discord application ([create one](https://discord.com/developers/applications)) with:
  - A **Bot** token (for the Discord bot)
  - **OAuth2** credentials — Client ID and Client Secret
  - `http://localhost:8000/auth/callback` added to **OAuth2 Redirects**

### Running locally

**Bot only:**

```bash
git clone <your-repo-url>
cd reminder-bot

python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

pip install -r bot/requirements.txt

cp .env.example .env
# Set DISCORD_TOKEN in .env

python bot/bot.py
```

**API only:**

```bash
pip install -r api/requirements.txt

# Set DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, JWT_SECRET in .env

uvicorn api.main:app --reload
# Docs at http://localhost:8000/docs
```

### Running with Docker

```bash
cp .env.example .env
# Fill in all required variables (see Environment Variables below)

# Build and start both services
docker compose up --build -d

# Logs
docker compose logs -f bot
docker compose logs -f api

# Stop
docker compose down
```

The database is stored in `./data/reminders.db` on the host (bind-mounted into both containers). It survives rebuilds and restarts.

---

## Environment Variables

| Variable | Required for | Description |
|---|---|---|
| `DISCORD_TOKEN` | Bot | Discord bot token |
| `DISCORD_CLIENT_ID` | API | OAuth2 app client ID |
| `DISCORD_CLIENT_SECRET` | API | OAuth2 app client secret |
| `DISCORD_REDIRECT_URI` | API | Must match the redirect URI in your Discord app. Default: `http://localhost:8000/auth/callback` |
| `JWT_SECRET` | API | Random secret for signing JWTs. Generate with: `openssl rand -hex 32` |
| `FRONTEND_URL` | API | If set, the OAuth callback redirects to `<FRONTEND_URL>?token=<jwt>` instead of returning JSON |
| `DB_PATH` | Both | Path to the SQLite file. Docker sets this to `/app/data/reminders.db` |

---

## Project Structure

```
reminder-bot/
├── bot/                        # Discord bot service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── bot.py                  # Entry point — bot setup, graceful shutdown
│   ├── scheduler.py            # APScheduler — job scheduling, reminder firing, recovery
│   ├── utils.py                # Date parsing, formatting helpers, timezone constants
│   ├── cogs/
│   │   └── reminders.py        # Slash commands (/reminder, /reminders, /delete-reminder, /timezone)
│   └── views/
│       └── reminder_views.py   # Discord UI — modals, buttons, selects, embeds
├── api/                        # REST API service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # FastAPI app, CORS, lifespan
│   ├── auth.py                 # Discord OAuth2 flow, JWT creation and verification
│   ├── models.py               # Pydantic request/response schemas
│   └── routes/
│       ├── reminders.py        # CRUD endpoints for reminders
│       └── users.py            # User profile and timezone endpoints
├── shared/
│   └── database.py             # SQLite layer shared by both services
├── data/                       # SQLite database volume (gitignored)
├── docker-compose.yml
└── .env.example
```

Both Docker images are built from the project root so they can share the `shared/` module. The bot sets `PYTHONPATH=/app/bot:/app` and the API sets `PYTHONPATH=/app`.

---

## Technical Notes

- **Timezone handling** — user input is parsed in the user's timezone and stored as UTC ISO strings. Neither service reads the host system's timezone.
- **Shared database** — both the bot and the API read/write the same SQLite file via a shared Docker volume. SQLite WAL mode (`PRAGMA journal_mode=WAL`) prevents corruption under concurrent access.
- **Graceful shutdown** — the bot handles `SIGTERM` (Docker stop) and `SIGINT` (Ctrl-C) to shut down APScheduler and close the Discord connection before the process exits.
- **Repeat drift prevention** — for daily and weekly reminders, the next occurrence always preserves the original scheduled time-of-day, even when recovering from a missed fire.
- **Discord API errors** — `Forbidden` (DMs closed) and `NotFound` (deleted account) automatically deactivate the reminder.
- **JWT expiry** — tokens are valid for 7 days. The API returns `401` on expired or tampered tokens.
