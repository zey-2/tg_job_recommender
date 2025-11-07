"""Configuration settings for the Telegram Job Bot."""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Adzuna API
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "job_bot.db")

# Adaptive Learning Parameters
TOP_K = int(os.getenv("TOP_K", 8))
REALTIME_MIN = int(os.getenv("REALTIME_MIN", 2))
REALTIME_MAX = int(os.getenv("REALTIME_MAX", 3))
DAILY_COUNT = int(os.getenv("DAILY_COUNT", 5))
DECAY = float(os.getenv("DECAY", 0.98))
LIKE_BOOST = float(os.getenv("LIKE_BOOST", 1.0))
DISLIKE_PENALTY = float(os.getenv("DISLIKE_PENALTY", -1.0))
NEGATIVE_PROMOTE_AT = float(os.getenv("NEGATIVE_PROMOTE_AT", -2.0))
DEFAULT_NOTIFICATIONS = os.getenv("DEFAULT_NOTIFICATIONS", "true").lower() == "true"
DEFAULT_NOTIFICATION_TIME = os.getenv("DEFAULT_NOTIFICATION_TIME", "09:00")

# Timezone
DEFAULT_TIMEZONE = "Asia/Singapore"
