"""Main entry point for the Telegram Job Bot."""
import asyncio
import os
import sys
import platform
import logging
from telegram import Update
from telegram.ext import Application
from bot import get_bot
from scheduler import run_digest, start_background_scheduler, shutdown_scheduler
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def run_polling():
    """Run bot in polling mode (for development)."""
    logger.info("Starting bot in polling mode...")
    print("Starting bot in polling mode...")
    
    # Create application
    job_bot = get_bot()
    # Ask the bot to start the scheduler on initialization (post_init) if enabled
    application = job_bot.create_application(start_scheduler=config.SCHEDULER_ENABLED)

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    print("Bot is running. Press Ctrl+C to stop.")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        # Ensure scheduler shutdown (if it was created)
        try:
            shutdown_scheduler(None)
        except Exception:
            logger.exception("Failed to shutdown scheduler: ")


def run_webhook(port: int = 8080):
    """Webhook mode removed: this project is polling-only.
    For manual digest runs, use 'python main.py digest' (keeps working).
    """
    raise RuntimeError("Webhook mode has been removed. Please use polling mode instead: 'python main.py'")
def run_digest_job():
    """Run the daily digest job (sync wrapper)."""
    asyncio.run(run_digest())


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "digest":
            # Run digest job
            print("Running digest job...")
            run_digest_job()
        elif sys.argv[1] == "webhook":
            # Webhook mode is no longer supported
            print("Webhook mode has been removed; please use polling mode (default).")
        else:
            print("Unknown command. Use 'python main.py [polling|webhook|digest]'")
    else:
        # Default to polling mode for development
        run_polling()
