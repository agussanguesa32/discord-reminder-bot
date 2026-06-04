import os
import signal
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from shared import database as db
import scheduler as sched

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("reminder-bot")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from the .env file")


class ReminderBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.dm_messages = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        try:
            await self.load_extension("cogs.reminders")
            logger.info("Loaded extension: cogs.reminders")
        except Exception as e:
            logger.critical("Failed to load extension cogs.reminders: %s", e, exc_info=e)
            raise

        self.tree.on_error = self._on_tree_error

        try:
            await self.tree.sync()
            logger.info("Slash commands synced globally.")
        except discord.HTTPException as e:
            logger.error("Failed to sync slash commands: %s", e)

    async def on_ready(self):
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        sched.set_bot(self)
        if not sched.scheduler.running:
            sched.scheduler.start()
            logger.info("Scheduler started.")
            sched.load_all_reminders()
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="your reminders ⏰",
            )
        )

    async def on_disconnect(self):
        logger.warning("Bot disconnected from Discord.")

    async def on_resumed(self):
        logger.info("Bot session resumed.")

    async def _on_tree_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(
            "Unhandled slash command error in /%s: %s",
            interaction.command.name if interaction.command else "unknown",
            error,
            exc_info=error,
        )
        msg = "❌ An unexpected error occurred. Please try again."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException as e:
            logger.warning("Could not send error message to user: %s", e)


async def main():
    db.init_db()
    logger.info("Database initialized.")
    bot = ReminderBot()

    loop = asyncio.get_running_loop()

    _shutting_down = False

    async def shutdown(sig: signal.Signals):
        nonlocal _shutting_down
        if _shutting_down:
            logger.debug("Shutdown already in progress — ignoring duplicate signal %s.", sig.name)
            return
        _shutting_down = True
        logger.info("Received %s — shutting down gracefully.", sig.name)
        if sched.scheduler.running:
            sched.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")
        await bot.close()
        logger.info("Bot closed.")

    # SIGTERM is sent by Docker on `docker stop` / `docker compose down`.
    # SIGINT handles Ctrl-C in local dev. Windows doesn't support add_signal_handler,
    # so we fall back silently — asyncio.run() still handles KeyboardInterrupt there.
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
        except NotImplementedError:
            pass

    async with bot:
        try:
            await bot.start(TOKEN)
        except discord.LoginFailure:
            logger.critical("Invalid DISCORD_TOKEN — check your .env file.")
            raise


if __name__ == "__main__":
    asyncio.run(main())
