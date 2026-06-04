import logging

import discord
from discord.ext import commands
from discord import app_commands
import pytz

import database as db
import scheduler as sched
from utils import format_repeat, format_next_run, format_advance_notice, next_run_utc, discord_ts, COMMON_TIMEZONES
from views.reminder_views import QuickTimeView, ReminderListView, DeleteReminderView

logger = logging.getLogger(__name__)


class RemindersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /reminder ────────────────────────────────────────────────────────────

    @app_commands.command(name="reminder", description="Create a new reminder")
    async def create_reminder(self, interaction: discord.Interaction):
        try:
            tz = db.get_user_timezone(interaction.user.id)
        except Exception as e:
            logger.error("DB error fetching timezone for user %s: %s", interaction.user.id, e, exc_info=e)
            await interaction.response.send_message(
                "❌ Failed to load your settings. Please try again.", ephemeral=True
            )
            return

        view = QuickTimeView(user_timezone=tz, user_id=interaction.user.id)
        embed = discord.Embed(
            title="⏰ New reminder — when?",
            description="Pick a quick preset or choose a custom date and time.",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── /reminders ───────────────────────────────────────────────────────────

    @app_commands.command(name="reminders", description="View all your active reminders")
    async def list_reminders(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            reminders = db.get_user_reminders(interaction.user.id)
        except Exception as e:
            logger.error("DB error fetching reminders for user %s: %s", interaction.user.id, e, exc_info=e)
            await interaction.followup.send(
                "❌ Failed to load your reminders. Please try again.", ephemeral=True
            )
            return

        if not reminders:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📭 No reminders",
                    description="You have no active reminders. Use `/reminder` to create one.",
                    color=discord.Color.greyple(),
                ),
                ephemeral=True,
            )
            return

        view = ReminderListView(reminders, interaction.user)
        embed = _build_list_embed(reminders, interaction.user)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # ── /delete-reminder ─────────────────────────────────────────────────────

    @app_commands.command(name="delete-reminder", description="Delete one of your reminders")
    async def delete_reminder(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            reminders = db.get_user_reminders(interaction.user.id)
        except Exception as e:
            logger.error("DB error fetching reminders for user %s: %s", interaction.user.id, e, exc_info=e)
            await interaction.followup.send(
                "❌ Failed to load your reminders. Please try again.", ephemeral=True
            )
            return

        if not reminders:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📭 No reminders",
                    description="You have no active reminders to delete.",
                    color=discord.Color.greyple(),
                ),
                ephemeral=True,
            )
            return

        view = DeleteReminderView(reminders, user_id=interaction.user.id)
        embed = discord.Embed(
            title="🗑️ Delete a reminder",
            description="Select the reminder you want to delete, then confirm.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # ── /timezone ────────────────────────────────────────────────────────────

    @app_commands.command(name="timezone", description="View or change your timezone")
    @app_commands.describe(zone="New timezone (e.g. America/New_York)")
    async def timezone(self, interaction: discord.Interaction, zone: str = None):
        if zone is None:
            try:
                current = db.get_user_timezone(interaction.user.id)
            except Exception as e:
                logger.error("DB error fetching timezone for user %s: %s", interaction.user.id, e, exc_info=e)
                await interaction.response.send_message(
                    "❌ Failed to load your timezone. Please try again.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title="🌍 Your timezone",
                description=f"`{current}`",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="Change it",
                value=(
                    "Use `/timezone zone:America/New_York` to update it.\n\n"
                    "**Common timezones:**\n"
                    + "\n".join(f"• `{z}`" for z in COMMON_TIMEZONES)
                ),
                inline=False,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            pytz.timezone(zone)
        except pytz.UnknownTimeZoneError:
            await interaction.response.send_message(
                f"❌ Unknown timezone: `{zone}`\n"
                "Use a valid tz database name, e.g. `America/Argentina/Buenos_Aires`.\n"
                "Full list: <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>",
                ephemeral=True,
            )
            return

        try:
            db.set_user_timezone(interaction.user.id, zone)
        except Exception as e:
            logger.error("DB error setting timezone for user %s: %s", interaction.user.id, e, exc_info=e)
            await interaction.response.send_message(
                "❌ Failed to save your timezone. Please try again.", ephemeral=True
            )
            return

        logger.info("User %s changed timezone to %s.", interaction.user.id, zone)
        await interaction.response.send_message(
            f"✅ Timezone updated to `{zone}`.", ephemeral=True
        )


def _build_list_embed(reminders, user) -> discord.Embed:
    embed = discord.Embed(
        title=f"🗓️ {user.display_name}'s reminders",
        color=discord.Color.blue(),
    )
    for r in reminders[:10]:
        dt = next_run_utc(r)
        repeat_str = format_repeat(r)
        advance_str = f" · {format_advance_notice(r['advance_notice'])}" if r["advance_notice"] else ""
        embed.add_field(
            name=f"#{r['id']} — {r['title']}",
            value=f"📅 {discord_ts(dt, 'f')} ({discord_ts(dt, 'R')})\n🔁 {repeat_str}{advance_str}",
            inline=False,
        )
    if len(reminders) > 10:
        embed.set_footer(text=f"Showing 10 of {len(reminders)} reminders.")
    return embed


async def setup(bot):
    await bot.add_cog(RemindersCog(bot))
