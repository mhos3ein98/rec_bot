# =============================================================================
# bot.py
# Entry point. Wires up the bot, dispatcher, and FSM storage, then polls.
# Run: python bot.py
#
# On startup we explicitly call set_chat_menu_button() to disable Telegram's
# native floating hamburger button (the one in the text-input bar set via
# BotFather). That button is a platform-level UI element completely separate
# from our InlineKeyboardMarkup rows. Resetting it ensures users only ever
# see the inline hamburger row we build inside each keyboard.
# =============================================================================

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonCommands, BotCommand

from config import TOKEN
from handlers import router

# ---------------------------------------------------------------------------
# Logging - console + rotating file
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    Path("data").mkdir(exist_ok=True)

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)

    # ── Setup the native Telegram Menu Button (☰) ────────────────────────────
    # Set up the bot commands so the built-in ☰ menu button displays them
    commands = [
        BotCommand(command="create", description="📁 Create Folder"),
        BotCommand(command="continue", description="📂 Continue Folder"),
        BotCommand(command="send", description="📤 Send Receipts"),
        BotCommand(command="accounting", description="📊 Accounting"),
        BotCommand(command="admins", description="👤 Admins"),
        BotCommand(command="menu", description="🏠 Main Menu"),
    ]
    try:
        await bot.set_my_commands(commands)
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Native Telegram menu button and commands configured.")
    except Exception as exc:
        logger.warning("Could not setup native menu button/commands: %s", exc)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
