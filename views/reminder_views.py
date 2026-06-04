import logging
from datetime import datetime

import discord
from discord.ui import Modal, TextInput, View, Button, Select
import pytz

import database as db
import scheduler as sched
from utils import parse_datetime_with_tz, format_repeat, format_next_run, UNIT_LABELS, DAY_LABELS, DEFAULT_TZ

logger = logging.getLogger(__name__)


async def _safe_respond(interaction: discord.Interaction, **kwargs):
    """Send a response, falling back to followup if the interaction was already acknowledged."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
    except discord.NotFound:
        logger.warning("Interaction expired before response could be sent (user: %s)", interaction.user.id)
    except discord.HTTPException as e:
        logger.error("Failed to respond to interaction for user %s: %s", interaction.user.id, e)


# ─────────────────────────────────────────────────────────────────────────────
# Create reminder modal
# ─────────────────────────────────────────────────────────────────────────────

class CreateReminderModal(Modal, title="➕ New Reminder"):
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
    date_time = TextInput(
        label="Date & time",
        placeholder="MM/DD/YYYY HH:MM  (e.g. 06/25/2025 14:30)",
        max_length=20,
    )
    advance_notice = TextInput(
        label="Advance notice in minutes (0 = none)",
        placeholder="e.g. 30",
        default="0",
        max_length=4,
    )

    def __init__(self, user_timezone: str = DEFAULT_TZ):
        super().__init__()
        self.user_timezone = user_timezone

    async def on_submit(self, interaction: discord.Interaction):
        try:
            advance = int(self.advance_notice.value.strip() or "0")
            if advance < 0:
                raise ValueError("Negative advance notice")
        except ValueError:
            await _safe_respond(
                interaction,
                content="❌ Advance notice must be a non-negative integer (e.g. `30`).",
                ephemeral=True,
            )
            return

        next_run = parse_datetime_with_tz(self.date_time.value, self.user_timezone)
        if not next_run:
            await _safe_respond(
                interaction,
                content=(
                    "❌ Invalid date format. Use `MM/DD/YYYY HH:MM` or `DD/MM/YYYY HH:MM`.\n"
                    "Example: `06/25/2025 14:30`"
                ),
                ephemeral=True,
            )
            return

        now_utc = datetime.now(pytz.utc)
        if next_run <= now_utc:
            await _safe_respond(
                interaction,
                content="❌ The date and time must be in the future.",
                ephemeral=True,
            )
            return

        tz = pytz.timezone(self.user_timezone)
        local_dt = next_run.astimezone(tz)
        tz_label = self.user_timezone.split("/")[-1].replace("_", " ")

        view = RepeatConfigView(
            r_title=self.r_title.value,
            description=self.description.value,
            next_run=next_run,
            advance=advance,
            user_timezone=self.user_timezone,
            user_id=interaction.user.id,
        )
        embed = discord.Embed(
            title="⚙️ Set repeat schedule",
            description=(
                f"**{self.r_title.value}**\n"
                f"📅 {local_dt.strftime('%m/%d/%Y %H:%M')} ({tz_label})\n\n"
                "How often should this reminder repeat?"
            ),
            color=discord.Color.blurple(),
        )
        await _safe_respond(interaction, embed=embed, view=view, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error("Error in CreateReminderModal for user %s: %s", interaction.user.id, error, exc_info=error)
        await _safe_respond(interaction, content="❌ Something went wrong. Please try again.", ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Repeat configuration view
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

    @discord.ui.button(label="No repeat", style=discord.ButtonStyle.secondary, emoji="1️⃣")
    async def no_repeat(self, interaction: discord.Interaction, button: Button):
        await self._save_and_confirm(interaction, "none", 0, None, None)

    @discord.ui.button(label="Daily", style=discord.ButtonStyle.primary, emoji="📆")
    async def daily(self, interaction: discord.Interaction, button: Button):
        await self._save_and_confirm(interaction, "daily", 1, "days", None)

    @discord.ui.button(label="Weekly (pick days)", style=discord.ButtonStyle.primary, emoji="📅")
    async def weekly(self, interaction: discord.Interaction, button: Button):
        view = WeeklyDayPickerView(
            r_title=self.r_title,
            description=self.r_description,
            next_run=self.next_run,
            advance=self.advance,
            user_timezone=self.user_timezone,
            user_id=self.user_id,
        )
        embed = discord.Embed(
            title="📅 Pick days of the week",
            description="Select one or more days on which this reminder will repeat.",
            color=discord.Color.blurple(),
        )
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except discord.HTTPException as e:
            logger.error("Failed to show day picker for user %s: %s", interaction.user.id, e)

    @discord.ui.button(label="Custom interval", style=discord.ButtonStyle.success, emoji="⏱️")
    async def custom_interval(self, interaction: discord.Interaction, button: Button):
        modal = IntervalModal(
            r_title=self.r_title,
            description=self.r_description,
            next_run=self.next_run,
            advance=self.advance,
            user_timezone=self.user_timezone,
            user_id=self.user_id,
        )
        try:
            await interaction.response.send_modal(modal)
        except discord.HTTPException as e:
            logger.error("Failed to send IntervalModal for user %s: %s", interaction.user.id, e)

    async def _save_and_confirm(self, interaction, repeat_type, interval, unit, days):
        try:
            reminder_id = db.create_reminder(
                user_id=self.user_id,
                title=self.r_title,
                description=self.r_description,
                next_run=self.next_run,
                repeat_type=repeat_type,
                repeat_interval=interval,
                repeat_unit=unit,
                repeat_days=days,
                advance_notice=self.advance,
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
# Weekly day picker view
# ─────────────────────────────────────────────────────────────────────────────

WEEKDAY_OPTIONS = [
    discord.SelectOption(label="Monday", value="monday", emoji="1️⃣"),
    discord.SelectOption(label="Tuesday", value="tuesday", emoji="2️⃣"),
    discord.SelectOption(label="Wednesday", value="wednesday", emoji="3️⃣"),
    discord.SelectOption(label="Thursday", value="thursday", emoji="4️⃣"),
    discord.SelectOption(label="Friday", value="friday", emoji="5️⃣"),
    discord.SelectOption(label="Saturday", value="saturday", emoji="6️⃣"),
    discord.SelectOption(label="Sunday", value="sunday", emoji="7️⃣"),
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

        self.day_select = Select(
            placeholder="Pick days...",
            options=WEEKDAY_OPTIONS,
            min_values=1,
            max_values=7,
        )
        self.day_select.callback = self.day_selected
        self.add_item(self.day_select)

        confirm_btn = Button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
        confirm_btn.callback = self.confirm
        self.add_item(confirm_btn)

    async def on_timeout(self):
        logger.debug("WeeklyDayPickerView timed out for user %s", self.user_id)

    async def day_selected(self, interaction: discord.Interaction):
        self.selected_days = self.day_select.values
        try:
            await interaction.response.defer()
        except discord.HTTPException:
            pass

    async def confirm(self, interaction: discord.Interaction):
        if not self.selected_days:
            await _safe_respond(interaction, content="❌ Please select at least one day.", ephemeral=True)
            return

        days_str = ",".join(self.selected_days)
        try:
            reminder_id = db.create_reminder(
                user_id=self.user_id,
                title=self.r_title,
                description=self.r_description,
                next_run=self.next_run,
                repeat_type="weekly",
                repeat_interval=1,
                repeat_unit="weeks",
                repeat_days=days_str,
                advance_notice=self.advance,
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
    every = TextInput(
        label="Repeat every (number)",
        placeholder="e.g. 2",
        max_length=5,
    )
    unit = TextInput(
        label="Unit: minutes / hours / days / weeks / months",
        placeholder="days",
        max_length=10,
    )

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
                raise ValueError("Must be positive")
        except ValueError:
            await _safe_respond(
                interaction,
                content="❌ The interval must be a positive integer (e.g. `2`).",
                ephemeral=True,
            )
            return

        unit = self.unit.value.strip().lower()
        valid_units = {"minutes", "hours", "days", "weeks", "months"}
        if unit not in valid_units:
            await _safe_respond(
                interaction,
                content=f"❌ Invalid unit. Use one of: `{', '.join(sorted(valid_units))}`",
                ephemeral=True,
            )
            return

        try:
            reminder_id = db.create_reminder(
                user_id=self.user_id,
                title=self.r_title,
                description=self.r_description,
                next_run=self.next_run,
                repeat_type="interval",
                repeat_interval=interval,
                repeat_unit=unit,
                repeat_days=None,
                advance_notice=self.advance,
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

        if reminders:
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
# Reminder detail view (actions)
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
            logger.error("Error deleting reminder #%s for user %s: %s", reminder_id, interaction.user.id, e, exc_info=e)
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
            logger.error("Failed to update message after delete for reminder #%s: %s", reminder_id, e)

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.secondary, emoji="⏸️")
    async def toggle(self, interaction: discord.Interaction, button: Button):
        reminder_id = self.reminder["id"]
        if str(self.reminder["user_id"]) != str(interaction.user.id):
            await _safe_respond(interaction, content="❌ You don't own this reminder.", ephemeral=True)
            return

        current_active = self.reminder["active"]
        new_active = 0 if current_active else 1

        try:
            db.update_reminder_field(reminder_id, str(interaction.user.id), "active", new_active)
        except Exception as e:
            logger.error("DB error toggling reminder #%s for user %s: %s", reminder_id, interaction.user.id, e, exc_info=e)
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
# Embed helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_confirmation_embed(
    reminder_id, title, description, next_run_utc,
    repeat_type, interval, unit, days,
    advance, timezone,
) -> discord.Embed:
    tz = pytz.timezone(timezone)
    local_dt = next_run_utc.astimezone(tz)
    tz_label = timezone.split("/")[-1].replace("_", " ")

    embed = discord.Embed(title="✅ Reminder created", color=discord.Color.green())
    embed.add_field(name="📌 Title", value=title, inline=False)
    if description:
        embed.add_field(name="📝 Description", value=description, inline=False)
    embed.add_field(
        name="📅 First run",
        value=f"{local_dt.strftime('%m/%d/%Y %H:%M')} ({tz_label})",
        inline=True,
    )

    if repeat_type == "none":
        repeat_str = "No repeat"
    elif repeat_type == "daily":
        repeat_str = "Daily"
    elif repeat_type == "weekly":
        day_list = [DAY_LABELS.get(d.strip(), d) for d in (days or "").split(",") if d.strip()]
        repeat_str = "Weekly · " + ", ".join(day_list)
    elif repeat_type == "interval":
        unit_label = UNIT_LABELS.get(unit, unit)
        repeat_str = f"Every {interval} {unit_label}"
    else:
        repeat_str = repeat_type

    embed.add_field(name="🔁 Repeat", value=repeat_str, inline=True)
    embed.add_field(
        name="⏰ Advance notice",
        value=f"{advance} min before" if advance else "None",
        inline=True,
    )
    embed.set_footer(text=f"ID #{reminder_id} · Use /reminders to see all your reminders")
    return embed


def _build_detail_embed(reminder) -> discord.Embed:
    tz = pytz.timezone(reminder["timezone"])
    next_run_utc = datetime.fromisoformat(reminder["next_run"]).replace(tzinfo=pytz.utc)
    local_dt = next_run_utc.astimezone(tz)
    tz_label = reminder["timezone"].split("/")[-1].replace("_", " ")
    status = "✅ Active" if reminder["active"] else "⏸️ Paused"

    embed = discord.Embed(
        title=f"#{reminder['id']} — {reminder['title']}",
        color=discord.Color.green() if reminder["active"] else discord.Color.orange(),
    )
    if reminder["description"]:
        embed.add_field(name="📝 Description", value=reminder["description"], inline=False)
    embed.add_field(
        name="📅 Next run",
        value=f"{local_dt.strftime('%m/%d/%Y %H:%M')} ({tz_label})",
        inline=True,
    )
    embed.add_field(name="🔁 Repeat", value=format_repeat(reminder), inline=True)
    embed.add_field(
        name="⏰ Advance notice",
        value=f"{reminder['advance_notice']} min before" if reminder["advance_notice"] else "None",
        inline=True,
    )
    embed.add_field(name="Status", value=status, inline=True)
    return embed
