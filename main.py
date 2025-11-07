"""Main entry point for the Telegram Job Bot."""
import asyncio
import sys
import platform
import logging
from telegram import Update
from telegram.ext import Application
from bot import get_bot
from scheduler import run_digest
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
    application = job_bot.create_application()
    
    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    print("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def run_webhook(port: int = 8080):
    """Run bot in webhook mode (for Cloud Run)."""
    print(f"Starting bot in webhook mode on port {port}...")
    
    # Create application
    job_bot = get_bot()
    application = job_bot.create_application()
    
    # Setup webhook (URL should be set in Cloud Run environment)
    webhook_url = f"https://your-cloud-run-url/webhook"
    
    # Start webhook server
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/webhook",
        webhook_url=webhook_url
    )
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
            # Run in webhook mode
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
            run_webhook(port)
        else:
            print("Unknown command. Use 'python main.py [polling|webhook|digest]'")
    else:
        # Default to polling mode for development
        run_polling()
