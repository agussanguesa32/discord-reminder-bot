# Reminder Bot

A personal Discord reminder bot that communicates exclusively via **Direct Messages**. Create reminders with flexible repeat schedules, advance notifications, and full persistence across restarts.

---

## Features

- **Create reminders** via an interactive modal — title, description, date/time, and advance notice
- **Repeat options** — no repeat, daily, weekly (pick specific days), or a fully custom interval (every N minutes / hours / days / weeks / months)
- **Advance notice** — get notified X minutes before the reminder fires
- **Persistent** — all reminders survive bot restarts; missed ones are delivered automatically on next startup
- **Per-user timezone** — defaults to `America/Argentina/Buenos_Aires`, configurable per user
- **Pause / Resume / Delete** reminders without recreating them
- **Full error handling** — DB errors, Discord API errors, and invalid input all produce clear messages

---

## Commands

| Command | Description |
|---|---|
| `/reminder` | Create a new reminder |
| `/reminders` | List all your active reminders |
| `/delete-reminder id:<N>` | Delete a reminder by its ID |
| `/timezone` | View your current timezone |
| `/timezone zone:<tz>` | Change your timezone (e.g. `America/New_York`) |

---

## Creating a Reminder — Step by Step

1. **Run `/reminder`** — a modal opens with four fields:
   - **Title** — short name for the reminder (required)
   - **Description** — optional details
   - **Date & time** — accepts `MM/DD/YYYY HH:MM` or `DD/MM/YYYY HH:MM` in your configured timezone
   - **Advance notice** — minutes before the reminder to send a preview notification (`0` = disabled)

2. **Choose a repeat schedule** — four buttons appear after submitting the modal:
   - **No repeat** — fires once and is done
   - **Daily** — repeats every day at the same time
   - **Weekly (pick days)** — select one or more weekdays from a dropdown, then confirm
   - **Custom interval** — enter a number and a unit (`minutes`, `hours`, `days`, `weeks`, `months`)

3. **Confirmation embed** is shown with all the details and the assigned ID.

---

## Reminder Notifications

**On time:**
> 🔔 **Title**
> Description: ...
> Scheduled for: 06/25/2025 14:30 (Buenos Aires)

**Advance notice (e.g. 30 min before):**
> ⏰ **Upcoming reminder: Title**
> Scheduled for: 06/25/2025 14:30
> 30 min advance notice · ID #5

**Delivered late (bot was offline):**
> 🔔 **Title** *(yellow)*
> ⚠️ This reminder was delivered late because the bot was offline.

---

## Viewing & Managing Reminders

`/reminders` shows up to 10 active reminders in an embed and a dropdown to select any one for details.

The detail view includes two action buttons:
- **🗑️ Delete** — permanently removes the reminder and cancels all scheduled jobs
- **⏸️ Pause / Resume** — suspends or reactivates without losing configuration

---

## Timezone

The default timezone for all users is `America/Argentina/Buenos_Aires` (UTC−3).

To change it:
```
/timezone zone:America/New_York
```

All date/time input and output uses your configured timezone. The bot stores everything in UTC internally, so it is fully independent of the server's system timezone.

A list of valid timezone names can be found at:
https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

> **Note:** changing your timezone does not retroactively update existing reminders. Each reminder stores the timezone it was created with.

---

## Persistence & Recovery

Reminders are stored in a SQLite database (`data/reminders.db`). On every startup the bot:

1. Loads all active reminders from the DB
2. Schedules future ones normally
3. **Delivers missed ones immediately** (within 10 seconds) with a late-delivery warning

For repeating reminders, the chain continues correctly after recovery — the next occurrence is calculated from the original scheduled time, not from "now", so the time of day never drifts.

---

## Setup

### Prerequisites

- Python 3.12+
- A Discord bot token ([create one here](https://discord.com/developers/applications))
- The bot must have the **Message Content** intent enabled and DM permissions

### Running locally

```bash
# Clone the repo and enter the directory
git clone <your-repo-url>
cd reminder-bot

# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the example env file and fill in your token
cp .env.example .env
# Edit .env and set DISCORD_TOKEN=your_token_here

# Run the bot
python bot.py
```

### Running with Docker

```bash
# Copy and fill in your token
cp .env.example .env
# Edit .env: DISCORD_TOKEN=your_token_here

# Build and start (detached)
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

The database is stored in `./data/reminders.db` on the host machine (bind-mounted into the container). It survives container rebuilds, restarts, and `docker compose down`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Your Discord bot token |
| `DB_PATH` | ❌ | Path to the SQLite file. Defaults to `reminders.db` next to `bot.py`. Docker sets this to `/app/data/reminders.db` |

---

## Project Structure

```
reminder-bot/
├── bot.py                  # Entry point — bot setup, signal handling, graceful shutdown
├── database.py             # SQLite layer — all reads/writes, WAL mode, connection management
├── scheduler.py            # APScheduler — job scheduling, reminder firing, recovery logic
├── utils.py                # Date parsing, formatting helpers, timezone constants
├── cogs/
│   └── reminders.py        # Slash commands (/reminder, /reminders, /delete-reminder, /timezone)
├── views/
│   └── reminder_views.py   # Discord UI — modals, buttons, selects, embeds
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Technical Notes

- **Timezone handling** — user input is parsed in the user's timezone and stored as UTC ISO strings. The bot never reads the host system's timezone.
- **WAL mode** — SQLite is configured with `PRAGMA journal_mode=WAL` on every connection, preventing DB corruption if the process is killed mid-write.
- **Graceful shutdown** — the bot handles `SIGTERM` (sent by Docker on `docker stop`) and `SIGINT` (Ctrl-C) to shut down APScheduler and close the Discord connection cleanly before the process exits.
- **Repeat drift prevention** — for daily and weekly reminders, the next occurrence always preserves the original scheduled time-of-day, even when recovering from a missed fire.
- **Discord API errors** — `Forbidden` (DMs closed by user) automatically deactivates the reminder. `NotFound` (user deleted their account) does the same. Transient HTTP errors are logged and retried on the next scheduled run.
