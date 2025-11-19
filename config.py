"""Configuration settings for the Telegram Job Bot."""
import os
from typing import Optional
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
MAX_NEW_POSITIVE_PER_FEEDBACK = int(os.getenv("MAX_NEW_POSITIVE_PER_FEEDBACK", 3))
MAX_NEW_NEGATIVE_PER_FEEDBACK = int(os.getenv("MAX_NEW_NEGATIVE_PER_FEEDBACK", 2))
# Manual keyword settings
# Max number of manual (positive) keywords a user can add
MAX_MANUAL_KEYWORDS = int(os.getenv("MAX_MANUAL_KEYWORDS", 4))
DEFAULT_NOTIFICATIONS = os.getenv("DEFAULT_NOTIFICATIONS", "true").lower() == "true"
DEFAULT_NOTIFICATION_TIME = os.getenv("DEFAULT_NOTIFICATION_TIME", "09:00")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

# Timezone
DEFAULT_TIMEZONE = "Asia/Singapore"

# Scheduler settings (self-scheduling background scheduler)
# Enable/disable the in-process scheduler (polling mode)
SCHEDULER_ENABLED = bool(int(os.getenv("SCHEDULER_ENABLED", "1")))
# Interval in seconds for scheduler to check for due digests (default: 60s)
SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
# APScheduler timezone name
SCHEDULER_TZ = os.getenv("SCHEDULER_TZ", DEFAULT_TIMEZONE)
# Scheduler job concurrency controls
SCHEDULER_MAX_INSTANCES = int(os.getenv("SCHEDULER_MAX_INSTANCES", "1"))
SCHEDULER_COALESCE = bool(int(os.getenv("SCHEDULER_COALESCE", "1")))
SCHEDULER_MISFIRE_GRACE_TIME = int(os.getenv("SCHEDULER_MISFIRE_GRACE_TIME", "300"))

# Optional distributed locking with Redis (future use)
SCHEDULER_USE_DISTRIBUTED_LOCK = bool(int(os.getenv("SCHEDULER_USE_DISTRIBUTED_LOCK", "0")))
REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
