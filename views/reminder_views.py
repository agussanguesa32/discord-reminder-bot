import logging
from datetime import datetime, timedelta

import discord
from discord.ui import Modal, TextInput, View, Button, Select
import pytz

import database as db
import scheduler as sched
from utils import (
    parse_date, build_datetime, preset_dt,
    format_advance_notice, format_repeat, format_next_run,
    next_run_utc, discord_ts, UNIT_LABELS, DAY_LABELS, DEFAULT_TZ,
)

logger = logging.getLogger(__name__)

HOUR_OPTIONS = [
    discord.SelectOption(label=f"{h:02d}:00", value=str(h))
    for h in range(24)
]

MINUTE_OPTIONS = [
    discord.SelectOption(label=f":{m:02d}", value=str(m))
    for m in range(0, 60, 5)
]

ADVANCE_DAY_OPTIONS = [
    discord.SelectOption(label="0 days", value="0", default=True),
    *[discord.SelectOption(label=f"{d} day{'s' if d > 1 else ''}", value=str(d)) for d in range(1, 8)]
]

ADVANCE_HOUR_OPTIONS = [
    discord.SelectOption(label="0 hours", value="0", default=True),
    *[discord.SelectOption(label=f"{h} hour{'s' if h > 1 else ''}", value=str(h)) for h in range(1, 24)]
]

ADVANCE_MINUTE_OPTIONS = [
    discord.SelectOption(label="0 min", value="0", default=True),
    *[discord.SelectOption(label=f"{m} min", value=str(m)) for m in range(5, 60, 5)]
]


async def _safe_respond(interaction: discord.Interaction, **kwargs):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except discord.NotFound:
        logger.warning("Interaction expired (user: %s)", interaction.user.id)
    except discord.HTTPException as e:
        logger.error("Failed to respond to interaction for user %s: %s", interaction.user.id, e)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Quick time picker
# ─────────────────────────────────────────────────────────────────────────────

class QuickTimeView(View):
    def __init__(self, user_timezone: str, user_id: int):
        super().__init__(timeout=180)
        self.user_timezone = user_timezone
        self.user_id = user_id

    async def on_timeout(self):
        logger.debug("QuickTimeView timed out for user %s", self.user_id)

    async def _open_details_modal(self, interaction: discord.Interaction, prefilled_dt: datetime):
        modal = ReminderDetailsModal(
            prefilled_dt=prefilled_dt,
            user_timezone=self.user_timezone,
            user_id=self.user_id,
        )
        try:
            await interaction.response.send_modal(modal)
        except discord.HTTPException as e:
            logger.error("Failed to send ReminderDetailsModal for user %s: %s", self.user_id, e)

    @discord.ui.button(label="In 30 min",          style=discord.ButtonStyle.secondary, row=0)
    async def in_30m(self, interaction: discord.Interaction, button: Button):
        await self._open_details_modal(interaction, preset_dt(self.user_timezone, 0, *_time_ahead(self.user_timezone, 30)))

    @discord.ui.button(label="In 1 hour",           style=discord.ButtonStyle.secondary, row=0)
    async def in_1h(self, interaction: discord.Interaction, button: Button):
        await self._open_details_modal(interaction, preset_dt(self.user_timezone, 0, *_time_ahead(self.user_timezone, 60)))

    @discord.ui.button(label="In 2 hours",          style=discord.ButtonStyle.secondary, row=0)
    async def in_2h(self, interaction: discord.Interaction, button: Button):
        await self._open_details_modal(interaction, preset_dt(self.user_timezone, 0, *_time_ahead(self.user_timezone, 120)))

    @discord.ui.button(label="In 4 hours",          style=discord.ButtonStyle.secondary, row=0)
    async def in_4h(self, interaction: discord.Interaction, button: Button):
        await self._open_details_modal(interaction, preset_dt(self.user_timezone, 0, *_time_ahead(self.user_timezone, 240)))

    @discord.ui.button(label="Tomorrow 9am",        style=discord.ButtonStyle.primary,   row=1)
    async def tmr_9(self, interaction: discord.Interaction, button: Button):
        await self._open_details_modal(interaction, preset_dt(self.user_timezone, 1, 9, 0))

    @discord.ui.button(label="Tomorrow 12pm",       style=discord.ButtonStyle.primary,   row=1)
    async def tmr_12(self, interaction: discord.Interaction, button: Button):
        await self._open_details_modal(interaction, preset_dt(self.user_timezone, 1, 12, 0))

    @discord.ui.button(label="Tomorrow 6pm",        style=discord.ButtonStyle.primary,   row=1)
    async def tmr_18(self, interaction: discord.Interaction, button: Button):
        await self._open_details_modal(interaction, preset_dt(self.user_timezone, 1, 18, 0))

    @discord.ui.button(label="📅 Custom date & time", style=discord.ButtonStyle.success, row=2)
    async def custom(self, interaction: discord.Interaction, button: Button):
        modal = CustomDateModal(user_timezone=self.user_timezone, user_id=self.user_id)
        try:
            await interaction.response.send_modal(modal)
        except discord.HTTPException as e:
            logger.error("Failed to send CustomDateModal for user %s: %s", self.user_id, e)


def _time_ahead(timezone: str, minutes: int):
    tz = pytz.timezone(timezone)
    target = datetime.now(tz) + timedelta(minutes=minutes)
    return target.hour, target.minute


# ─────────────────────────────────────────────────────────────────────────────
# Step 2a — Details modal for quick presets (Title + Description only)
# ─────────────────────────────────────────────────────────────────────────────

class ReminderDetailsModal(Modal, title="➕ Reminder details"):
    r_title = TextInput(
        label="Title",
        placeholder="e.g. Team meeting",
        max_length=100,
    )
    description = TextInput(
        label="Description (optional)",
        placeholder="Additional details...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, prefilled_dt: datetime, user_timezone: str, user_id: int):
        super().__init__()
        self.prefilled_dt = prefilled_dt
        self.user_timezone = user_timezone
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        now_utc = datetime.now(pytz.utc)
        if self.prefilled_dt <= now_utc:
            await _safe_respond(
                interaction,
                content="❌ That time is already in the past. Please create a new reminder.",
                ephemeral=True,
            )
            return

        view = AdvanceNoticeView(
            r_title=self.r_title.value,
            description=self.description.value,
            next_run=self.prefilled_dt,
            user_timezone=self.user_timezone,
            user_id=self.user_id,
        )
        embed = _advance_notice_embed(self.r_title.value, self.prefilled_dt)
        await _safe_respond(interaction, embed=embed, view=view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error("Error in ReminderDetailsModal for user %s: %s", interaction.user.id, error, exc_info=error)
        await _safe_respond(interaction, content="❌ Something went wrong. Please try again.", ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2b — Custom date modal (Title + Description + Date — 3 fields)
# ─────────────────────────────────────────────────────────────────────────────

class CustomDateModal(Modal, title="📅 Set date"):
    r_title = TextInput(
        label="Title",
        placeholder="e.g. Team meeting",
        max_length=100,
    )
    description = TextInput(
        label="Description (optional)",
        placeholder="Additional details...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500,
    )
    date_input = TextInput(
        label="Date (DD/MM/YYYY or DD/MM)",
        placeholder="e.g. 25/06/2025  or  25/06",
        max_length=12,
    )

    def __init__(self, user_timezone: str, user_id: int):
        super().__init__()
        self.user_timezone = user_timezone
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        date_local = parse_date(self.date_input.value, self.user_timezone)
        if not date_local:
            await _safe_respond(
                interaction,
                content=(
                    "❌ Invalid date format.\n"
                    "Use **DD/MM/YYYY** (e.g. `25/06/2025`) or **DD/MM** for the current year."
                ),
                ephemeral=True,
            )
            return

        view = TimePickerView(
            r_title=self.r_title.value,
            description=self.description.value,
            date_local=date_local,
            user_timezone=self.user_timezone,
            user_id=self.user_id,
        )
        embed = discord.Embed(
            title="🕐 Pick a time",
            description=f"**{self.r_title.value}** · {discord_ts(date_local, 'd')}\n\nSelect the hour and minute, then confirm.",
            color=discord.Color.blurple(),
        )
        await _safe_respond(interaction, embed=embed, view=view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error("Error in CustomDateModal for user %s: %s", interaction.user.id, error, exc_info=error)
        await _safe_respond(interaction, content="❌ Something went wrong. Please try again.", ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Time picker (hour + minute selects)
# ─────────────────────────────────────────────────────────────────────────────

class TimePickerView(View):
    def __init__(self, r_title, description, date_local, user_timezone, user_id):
        super().__init__(timeout=300)
        self.r_title = r_title
        self.r_description = description
        self.date_local = date_local
        self.user_timezone = user_timezone
        self.user_id = user_id
        self.selected_hour: int | None = None
        self.selected_minute: int | None = None

        hour_select = Select(placeholder="Hour (00–23)...", options=HOUR_OPTIONS, min_values=1, max_values=1, row=0)
        hour_select.callback = self._on_hour
        self.add_item(hour_select)

        minute_select = Select(placeholder="Minute (:00, :05 ...)...", options=MINUTE_OPTIONS, min_values=1, max_values=1, row=1)
        minute_select.callback = self._on_minute
        self.add_item(minute_select)

        confirm_btn = Button(label="Confirm time", style=discord.ButtonStyle.success, emoji="✅", row=2)
        confirm_btn.callback = self._confirm
        self.add_item(confirm_btn)

    async def on_timeout(self):
        logger.debug("TimePickerView timed out for user %s", self.user_id)

    async def _on_hour(self, interaction: discord.Interaction):
        self.selected_hour = int(interaction.data["values"][0])
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass

    async def _on_minute(self, interaction: discord.Interaction):
        self.selected_minute = int(interaction.data["values"][0])
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass

    async def _confirm(self, interaction: discord.Interaction):
        if self.selected_hour is None or self.selected_minute is None:
            await _safe_respond(interaction, content="❌ Please select both an hour and a minute first.", ephemeral=True)
            return

        next_run = build_datetime(self.date_local, self.selected_hour, self.selected_minute)
        now_utc = datetime.now(pytz.utc)
        if next_run <= now_utc:
            await _safe_respond(
                interaction,
                content=f"❌ {discord_ts(next_run, 'f')} is in the past. Please go back and pick a future date/time.",
                ephemeral=True,
            )
            return

        view = AdvanceNoticeView(
            r_title=self.r_title,
            description=self.r_description,
            next_run=next_run,
            user_timezone=self.user_timezone,
            user_id=self.user_id,
        )
        embed = _advance_notice_embed(self.r_title, next_run)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.HTTPException as e:
            logger.error("Failed to advance to AdvanceNoticeView for user %s: %s", self.user_id, e)


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Advance notice picker (days / hours / minutes selects)
# ─────────────────────────────────────────────────────────────────────────────

class AdvanceNoticeView(View):
    """
    Three independent selects for days, hours, and minutes.
    All default to 0 — leaving them untouched means no advance notice.
    """

    def __init__(self, r_title, description, next_run, user_timezone, user_id):
        super().__init__(timeout=300)
        self.r_title = r_title
        self.r_description = description
        self.next_run = next_run
        self.user_timezone = user_timezone
        self.user_id = user_id
        self.adv_days = 0
        self.adv_hours = 0
        self.adv_minutes = 0

        day_select = Select(
            placeholder="Days before (default: 0)...",
            options=ADVANCE_DAY_OPTIONS,
            min_values=1, max_values=1, row=0,
        )
        day_select.callback = self._on_days
        self.add_item(day_select)

        hour_select = Select(
            placeholder="Hours before (default: 0)...",
            options=ADVANCE_HOUR_OPTIONS,
            min_values=1, max_values=1, row=1,
        )
        hour_select.callback = self._on_hours
        self.add_item(hour_select)

        minute_select = Select(
            placeholder="Minutes before (default: 0)...",
            options=ADVANCE_MINUTE_OPTIONS,
            min_values=1, max_values=1, row=2,
        )
        minute_select.callback = self._on_minutes
        self.add_item(minute_select)

        skip_btn = Button(label="No advance notice", style=discord.ButtonStyle.secondary, emoji="⏭️", row=3)
        skip_btn.callback = self._skip
        self.add_item(skip_btn)

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅", row=3)
        confirm_btn.callback = self._confirm
        self.add_item(confirm_btn)

    async def on_timeout(self):
        logger.debug("AdvanceNoticeView timed out for user %s", self.user_id)

    async def _on_days(self, interaction: discord.Interaction):
        self.adv_days = int(interaction.data["values"][0])
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass

    async def _on_hours(self, interaction: discord.Interaction):
        self.adv_hours = int(interaction.data["values"][0])
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass

    async def _on_minutes(self, interaction: discord.Interaction):
        self.adv_minutes = int(interaction.data["values"][0])
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass

    async def _skip(self, interaction: discord.Interaction):
        await self._proceed(interaction, advance=0)

    async def _confirm(self, interaction: discord.Interaction):
        advance = self.adv_days * 1440 + self.adv_hours * 60 + self.adv_minutes
        await self._proceed(interaction, advance=advance)

    async def _proceed(self, interaction: discord.Interaction, advance: int):
        view = RepeatConfigView(
            r_title=self.r_title,
            description=self.r_description,
            next_run=self.next_run,
            advance=advance,
            user_timezone=self.user_timezone,
            user_id=self.user_id,
        )
        embed = discord.Embed(
            title="⚙️ How often should this repeat?",
            description=(
                f"**{self.r_title}**\n"
                f"📅 First occurrence: {discord_ts(self.next_run, 'f')}  ({discord_ts(self.next_run, 'R')})\n"
                + (f"⏰ Advance notice: {format_advance_notice(advance)}\n" if advance else "")
                + "\n"
                "**One time** — fires once, then it's done.\n"
                "**Daily / Weekly / Monthly / Yearly** — repeats at the same time on that schedule.\n"
                "**Custom interval** — every N hours / days / weeks."
            ),
            color=discord.Color.blurple(),
        )
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.HTTPException as e:
            logger.error("Failed to advance to RepeatConfigView for user %s: %s", self.user_id, e)


def _advance_notice_embed(title: str, next_run: datetime) -> discord.Embed:
    return discord.Embed(
        title="⏰ Set advance notice",
        description=(
            f"**{title}**\n"
            f"📅 {discord_ts(next_run, 'f')}  ·  {discord_ts(next_run, 'R')}\n\n"
            "How much in advance should the bot notify you?\n"
            "Leave all selectors at **0** or click **No advance notice** to skip."
        ),
        color=discord.Color.blurple(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Repeat configuration
# ─────────────────────────────────────────────────────────────────────────────

class RepeatConfigView(View):
    def __init__(self, r_title, description, next_run, advance, user_timezone, user_id):
        super().__init__(timeout=300)
        self.r_title = r_title
        self.r_description = description
        self.next_run = next_run
        self.advance = advance
        self.user_timezone = user_timezone
        self.user_id = user_id

    async def on_timeout(self):
        logger.debug("RepeatConfigView timed out for user %s", self.user_id)

    @discord.ui.button(label="One time",           style=discord.ButtonStyle.secondary, emoji="🔕", row=0)
    async def one_time(self, interaction: discord.Interaction, button: Button):
        await self._save_and_confirm(interaction, "none", 0, None, None)

    @discord.ui.button(label="Daily",              style=discord.ButtonStyle.primary,   emoji="📆", row=0)
    async def daily(self, interaction: discord.Interaction, button: Button):
        await self._save_and_confirm(interaction, "daily", 1, "days", None)

    @discord.ui.button(label="Weekly",             style=discord.ButtonStyle.primary,   emoji="📅", row=0)
    async def weekly(self, interaction: discord.Interaction, button: Button):
        view = WeeklyDayPickerView(
            r_title=self.r_title, description=self.r_description,
            next_run=self.next_run, advance=self.advance,
            user_timezone=self.user_timezone, user_id=self.user_id,
        )
        embed = discord.Embed(
            title="📅 Pick days of the week",
            description=(
                f"First occurrence: {discord_ts(self.next_run, 'f')}\n\n"
                "Select the weekdays on which this reminder will repeat **at the same time**."
            ),
            color=discord.Color.blurple(),
        )
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.HTTPException as e:
            logger.error("Failed to show day picker for user %s: %s", interaction.user.id, e)

    @discord.ui.button(label="Monthly",            style=discord.ButtonStyle.primary,   emoji="🗓️", row=1)
    async def monthly(self, interaction: discord.Interaction, button: Button):
        await self._save_and_confirm(interaction, "monthly", 1, None, None)

    @discord.ui.button(label="Yearly",             style=discord.ButtonStyle.primary,   emoji="🎯", row=1)
    async def yearly(self, interaction: discord.Interaction, button: Button):
        await self._save_and_confirm(interaction, "yearly", 1, None, None)

    @discord.ui.button(label="Custom interval",    style=discord.ButtonStyle.success,   emoji="⏱️", row=1)
    async def custom_interval(self, interaction: discord.Interaction, button: Button):
        modal = IntervalModal(
            r_title=self.r_title, description=self.r_description,
            next_run=self.next_run, advance=self.advance,
            user_timezone=self.user_timezone, user_id=self.user_id,
        )
        try:
            await interaction.response.send_modal(modal)
        except discord.HTTPException as e:
            logger.error("Failed to send IntervalModal for user %s: %s", interaction.user.id, e)

    async def _save_and_confirm(self, interaction, repeat_type, interval, unit, days):
        try:
            reminder_id = db.create_reminder(
                user_id=self.user_id, title=self.r_title, description=self.r_description,
                next_run=self.next_run, repeat_type=repeat_type, repeat_interval=interval,
                repeat_unit=unit, repeat_days=days, advance_notice=self.advance,
                tz_name=self.user_timezone,
            )
        except Exception as e:
            logger.error("DB error creating reminder for user %s: %s", self.user_id, e, exc_info=e)
            await _safe_respond(interaction, content="❌ Failed to save the reminder. Please try again.", ephemeral=True)
            return

        sched.schedule_new_reminder(reminder_id)
        embed = _build_confirmation_embed(
            reminder_id, self.r_title, self.r_description,
            self.next_run, repeat_type, interval, unit, days,
            self.advance, self.user_timezone,
        )
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except discord.HTTPException as e:
            logger.error("Failed to send confirmation for reminder #%s: %s", reminder_id, e)


# ─────────────────────────────────────────────────────────────────────────────
# Weekly day picker
# ─────────────────────────────────────────────────────────────────────────────

WEEKDAY_OPTIONS = [
    discord.SelectOption(label="Monday",    value="monday",    emoji="1️⃣"),
    discord.SelectOption(label="Tuesday",   value="tuesday",   emoji="2️⃣"),
    discord.SelectOption(label="Wednesday", value="wednesday", emoji="3️⃣"),
    discord.SelectOption(label="Thursday",  value="thursday",  emoji="4️⃣"),
    discord.SelectOption(label="Friday",    value="friday",    emoji="5️⃣"),
    discord.SelectOption(label="Saturday",  value="saturday",  emoji="6️⃣"),
    discord.SelectOption(label="Sunday",    value="sunday",    emoji="7️⃣"),
]


class WeeklyDayPickerView(View):
    def __init__(self, r_title, description, next_run, advance, user_timezone, user_id):
        super().__init__(timeout=300)
        self.r_title = r_title
        self.r_description = description
        self.next_run = next_run
        self.advance = advance
        self.user_timezone = user_timezone
        self.user_id = user_id
        self.selected_days: list[str] = []

        day_select = Select(placeholder="Pick days...", options=WEEKDAY_OPTIONS, min_values=1, max_values=7)
        day_select.callback = self._day_selected
        self.add_item(day_select)

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
        confirm_btn.callback = self._confirm
        self.add_item(confirm_btn)

    async def on_timeout(self):
        logger.debug("WeeklyDayPickerView timed out for user %s", self.user_id)

    async def _day_selected(self, interaction: discord.Interaction):
        self.selected_days = interaction.data["values"]
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass

    async def _confirm(self, interaction: discord.Interaction):
        if not self.selected_days:
            await _safe_respond(interaction, content="❌ Please select at least one day.", ephemeral=True)
            return

        days_str = ",".join(self.selected_days)
        try:
            reminder_id = db.create_reminder(
                user_id=self.user_id, title=self.r_title, description=self.r_description,
                next_run=self.next_run, repeat_type="weekly", repeat_interval=1,
                repeat_unit="weeks", repeat_days=days_str, advance_notice=self.advance,
                tz_name=self.user_timezone,
            )
        except Exception as e:
            logger.error("DB error creating weekly reminder for user %s: %s", self.user_id, e, exc_info=e)
            await _safe_respond(interaction, content="❌ Failed to save the reminder. Please try again.", ephemeral=True)
            return

        sched.schedule_new_reminder(reminder_id)
        embed = _build_confirmation_embed(
            reminder_id, self.r_title, self.r_description,
            self.next_run, "weekly", 1, "weeks", days_str,
            self.advance, self.user_timezone,
        )
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except discord.HTTPException as e:
            logger.error("Failed to send confirmation for reminder #%s: %s", reminder_id, e)


# ─────────────────────────────────────────────────────────────────────────────
# Custom interval modal
# ─────────────────────────────────────────────────────────────────────────────

class IntervalModal(Modal, title="⏱️ Custom interval"):
    every = TextInput(label="Repeat every (number)", placeholder="e.g. 2", max_length=5)
    unit  = TextInput(label="Unit: hours / days / weeks", placeholder="days", max_length=10)

    def __init__(self, r_title, description, next_run, advance, user_timezone, user_id):
        super().__init__()
        self.r_title = r_title
        self.r_description = description
        self.next_run = next_run
        self.advance = advance
        self.user_timezone = user_timezone
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            interval = int(self.every.value.strip())
            if interval <= 0:
                raise ValueError
        except ValueError:
            await _safe_respond(interaction, content="❌ The interval must be a positive integer (e.g. `2`).", ephemeral=True)
            return

        unit = self.unit.value.strip().lower()
        if unit not in {"hours", "days", "weeks"}:
            await _safe_respond(interaction, content="❌ Invalid unit. Use one of: `hours, days, weeks`", ephemeral=True)
            return

        try:
            reminder_id = db.create_reminder(
                user_id=self.user_id, title=self.r_title, description=self.r_description,
                next_run=self.next_run, repeat_type="interval", repeat_interval=interval,
                repeat_unit=unit, repeat_days=None, advance_notice=self.advance,
                tz_name=self.user_timezone,
            )
        except Exception as e:
            logger.error("DB error creating interval reminder for user %s: %s", self.user_id, e, exc_info=e)
            await _safe_respond(interaction, content="❌ Failed to save the reminder. Please try again.", ephemeral=True)
            return

        sched.schedule_new_reminder(reminder_id)
        embed = _build_confirmation_embed(
            reminder_id, self.r_title, self.r_description,
            self.next_run, "interval", interval, unit, None,
            self.advance, self.user_timezone,
        )
        await _safe_respond(interaction, embed=embed, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error("Error in IntervalModal for user %s: %s", interaction.user.id, error, exc_info=error)
        await _safe_respond(interaction, content="❌ Something went wrong. Please try again.", ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Reminder list view
# ─────────────────────────────────────────────────────────────────────────────

class ReminderListView(View):
    def __init__(self, reminders, user):
        super().__init__(timeout=120)
        self.reminders = reminders
        self.user = user

        options = [
            discord.SelectOption(
                label=f"#{r['id']} — {r['title'][:50]}",
                value=str(r["id"]),
                description=format_next_run(r),
            )
            for r in reminders[:25]
        ]
        select = Select(placeholder="View reminder details...", options=options)
        select.callback = self.show_detail
        self.add_item(select)

    async def on_timeout(self):
        logger.debug("ReminderListView timed out for user %s", self.user.id)

    async def show_detail(self, interaction: discord.Interaction):
        reminder_id = int(interaction.data["values"][0])
        try:
            reminder = db.get_reminder(reminder_id)
        except Exception as e:
            logger.error("DB error fetching reminder #%s: %s", reminder_id, e, exc_info=e)
            await _safe_respond(interaction, content="❌ Failed to load reminder details.", ephemeral=True)
            return
        if not reminder:
            await _safe_respond(interaction, content="❌ Reminder not found.", ephemeral=True)
            return
        embed = _build_detail_embed(reminder)
        view = ReminderDetailView(reminder)
        await _safe_respond(interaction, embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Reminder detail view (pause / resume / delete)
# ─────────────────────────────────────────────────────────────────────────────

class ReminderDetailView(View):
    def __init__(self, reminder):
        super().__init__(timeout=120)
        self.reminder = reminder

    async def on_timeout(self):
        logger.debug("ReminderDetailView timed out for reminder #%s", self.reminder["id"])

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete(self, interaction: discord.Interaction, button: Button):
        reminder_id = self.reminder["id"]
        if str(self.reminder["user_id"]) != str(interaction.user.id):
            await _safe_respond(interaction, content="❌ You don't own this reminder.", ephemeral=True)
            return
        try:
            sched.remove_reminder_jobs(reminder_id)
            db.delete_reminder(reminder_id, interaction.user.id)
        except Exception as e:
            logger.error("Error deleting reminder #%s: %s", reminder_id, e, exc_info=e)
            await _safe_respond(interaction, content="❌ Failed to delete the reminder.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🗑️ Reminder deleted",
            description=f"Reminder **#{reminder_id}** has been deleted.",
            color=discord.Color.red(),
        )
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except discord.HTTPException as e:
            logger.error("Failed to update message after delete for #%s: %s", reminder_id, e)

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.secondary, emoji="⏸️")
    async def toggle(self, interaction: discord.Interaction, button: Button):
        reminder_id = self.reminder["id"]
        if str(self.reminder["user_id"]) != str(interaction.user.id):
            await _safe_respond(interaction, content="❌ You don't own this reminder.", ephemeral=True)
            return
        new_active = 0 if self.reminder["active"] else 1
        try:
            db.update_reminder_field(reminder_id, str(interaction.user.id), "active", new_active)
        except Exception as e:
            logger.error("DB error toggling reminder #%s: %s", reminder_id, e, exc_info=e)
            await _safe_respond(interaction, content="❌ Failed to update the reminder.", ephemeral=True)
            return
        if new_active:
            sched.schedule_new_reminder(reminder_id)
            status = "✅ Reminder resumed"
        else:
            sched.remove_reminder_jobs(reminder_id)
            status = "⏸️ Reminder paused"
        await _safe_respond(interaction, content=f"{status} **#{reminder_id}**.", ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Delete reminder flow (selector + confirmation)
# ─────────────────────────────────────────────────────────────────────────────

class DeleteReminderView(View):
    def __init__(self, reminders, user_id: int):
        super().__init__(timeout=120)
        self.reminders = {str(r["id"]): r for r in reminders}
        self.user_id = user_id
        self.selected_id: str | None = None

        options = [
            discord.SelectOption(
                label=f"#{r['id']} — {r['title'][:50]}",
                value=str(r["id"]),
                description=format_next_run(r),
            )
            for r in reminders[:25]
        ]
        select = Select(placeholder="Select a reminder to delete...", options=options)
        select.callback = self._on_select
        self.add_item(select)

        self.confirm_btn = Button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", disabled=True)
        self.confirm_btn.callback = self._on_confirm
        self.add_item(self.confirm_btn)

        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
        cancel_btn.callback = self._on_cancel
        self.add_item(cancel_btn)

    async def on_timeout(self):
        logger.debug("DeleteReminderView timed out for user %s", self.user_id)

    async def _on_select(self, interaction: discord.Interaction):
        self.selected_id = interaction.data["values"][0]
        reminder = self.reminders[self.selected_id]
        self.confirm_btn.disabled = False
        dt = next_run_utc(reminder)
        embed = discord.Embed(title=f"🗑️ Delete reminder #{reminder['id']}?", color=discord.Color.red())
        embed.add_field(name="📌 Title", value=reminder["title"], inline=False)
        if reminder["description"]:
            embed.add_field(name="📝 Description", value=reminder["description"], inline=False)
        embed.add_field(name="📅 Next run", value=f"{discord_ts(dt, 'f')}  ·  {discord_ts(dt, 'R')}", inline=False)
        embed.add_field(name="🔁 Repeat", value=format_repeat(reminder), inline=True)
        embed.set_footer(text="This action cannot be undone.")
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.HTTPException as e:
            logger.error("Failed to update DeleteReminderView for user %s: %s", self.user_id, e)

    async def _on_confirm(self, interaction: discord.Interaction):
        if not self.selected_id:
            await _safe_respond(interaction, content="❌ No reminder selected.", ephemeral=True)
            return
        reminder_id = int(self.selected_id)
        try:
            sched.remove_reminder_jobs(reminder_id)
            deleted = db.delete_reminder(reminder_id, self.user_id)
        except Exception as e:
            logger.error("Error deleting reminder #%s for user %s: %s", reminder_id, self.user_id, e, exc_info=e)
            await _safe_respond(interaction, content="❌ Failed to delete the reminder.", ephemeral=True)
            return
        if not deleted:
            await _safe_respond(interaction, content="❌ Reminder not found or already deleted.", ephemeral=True)
            return
        logger.info("User %s deleted reminder #%s via selector.", self.user_id, reminder_id)
        embed = discord.Embed(
            title="✅ Reminder deleted",
            description=f"Reminder **#{reminder_id}** has been deleted.",
            color=discord.Color.green(),
        )
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except discord.HTTPException as e:
            logger.error("Failed to confirm deletion for #%s: %s", reminder_id, e)

    async def _on_cancel(self, interaction: discord.Interaction):
        embed = discord.Embed(title="✖️ Cancelled", description="No reminders were deleted.", color=discord.Color.greyple())
        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except discord.HTTPException as e:
            logger.error("Failed to cancel DeleteReminderView for user %s: %s", self.user_id, e)


# ─────────────────────────────────────────────────────────────────────────────
# Embed helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_confirmation_embed(
    reminder_id, title, description, next_run_utc_dt,
    repeat_type, interval, unit, days, advance, timezone,
) -> discord.Embed:
    embed = discord.Embed(title="✅ Reminder created", color=discord.Color.green())
    embed.add_field(name="📌 Title", value=title, inline=False)
    if description:
        embed.add_field(name="📝 Description", value=description, inline=False)
    embed.add_field(
        name="📅 First run",
        value=f"{discord_ts(next_run_utc_dt, 'f')}\n{discord_ts(next_run_utc_dt, 'R')}",
        inline=True,
    )
    if repeat_type == "none":
        repeat_str = "No repeat"
    elif repeat_type == "daily":
        repeat_str = "Daily"
    elif repeat_type == "weekly":
        day_list = [DAY_LABELS.get(d.strip(), d) for d in (days or "").split(",") if d.strip()]
        repeat_str = "Weekly · " + ", ".join(day_list)
    else:
        repeat_str = f"Every {interval} {UNIT_LABELS.get(unit, unit)}"

    embed.add_field(name="🔁 Repeat",         value=repeat_str,                      inline=True)
    embed.add_field(name="⏰ Advance notice",  value=format_advance_notice(advance),  inline=True)
    embed.set_footer(text=f"ID #{reminder_id} · Use /reminders to see all your reminders")
    return embed


def _build_detail_embed(reminder) -> discord.Embed:
    dt = next_run_utc(reminder)
    status = "✅ Active" if reminder["active"] else "⏸️ Paused"
    embed = discord.Embed(
        title=f"#{reminder['id']} — {reminder['title']}",
        color=discord.Color.green() if reminder["active"] else discord.Color.orange(),
    )
    if reminder["description"]:
        embed.add_field(name="📝 Description", value=reminder["description"], inline=False)
    embed.add_field(name="📅 Next run",       value=f"{discord_ts(dt, 'f')}\n{discord_ts(dt, 'R')}", inline=True)
    embed.add_field(name="🔁 Repeat",         value=format_repeat(reminder),                         inline=True)
    embed.add_field(name="⏰ Advance notice",  value=format_advance_notice(reminder["advance_notice"]), inline=True)
    embed.add_field(name="Status",             value=status,                                          inline=True)
    return embed
