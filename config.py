"""Configuration settings for the Telegram Job Bot."""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# FindSGJobs API
FINDSGJOBS_API_ENDPOINT = os.getenv("FINDSGJOBS_API_ENDPOINT", "https://www.findsgjobs.com/apis/job/search")
FINDSGJOBS_USE_SEARCHABLE = os.getenv("FINDSGJOBS_USE_SEARCHABLE", "false").lower() == "true"

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Database
# Default to new database filename for FindSGJobs migration
DATABASE_PATH = os.getenv("DATABASE_PATH", "job_bot_findsgjobs.db")

# Currency constants for FindSGJobs
CURRENCIES = {
	"SGD": 1275916990,
	"MYR": 1275916991,
	"USD": 1275916992,
	"IND": 1275916993
}

# Salary interval constants
SALARY_INTERVALS = {
	"hour": 1895,
	"day": 1896,
	"week": 1897,
	"month": 1898,
	"annual": 1899,
	"assignment": 610066362600001536
}

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
# Number of days to exclude recently shown jobs from recommendations
EXCLUDE_RECENT_DAYS = int(os.getenv("EXCLUDE_RECENT_DAYS", 3))
# Manual keyword settings
# Max number of manual (positive) keywords a user can add
MAX_MANUAL_KEYWORDS = int(os.getenv("MAX_MANUAL_KEYWORDS", 3))
#
# How many different keywords to try before falling back to recent jobs
MAX_KEYWORD_RETRIES = int(os.getenv("MAX_KEYWORD_RETRIES", 3))
DEFAULT_NOTIFICATIONS = os.getenv("DEFAULT_NOTIFICATIONS", "true").lower() == "true"
DEFAULT_NOTIFICATION_TIME = os.getenv("DEFAULT_NOTIFICATION_TIME", "09:00")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

# Timezone
DEFAULT_TIMEZONE = "Asia/Singapore"


def _str2bool(val, default=False):
	"""Parse a value that may be 'true'/'false', '1'/'0' or similar into bool.
	Returns default if unparseable.
	"""
	if val is None:
		return default
	if isinstance(val, bool):
		return val
	v = str(val).strip().lower()
	if v in ("1", "true", "yes", "on", "y"):
		return True
	if v in ("0", "false", "no", "off", "n"):
		return False
	return default

# Scheduler settings (self-scheduling background scheduler)
# Enable/disable the in-process scheduler (polling mode)
SCHEDULER_ENABLED = _str2bool(os.getenv("SCHEDULER_ENABLED", "1"), True)
# Interval in seconds for scheduler to check for due digests (default: 60s)
SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
# APScheduler timezone name
SCHEDULER_TZ = os.getenv("SCHEDULER_TZ", DEFAULT_TIMEZONE)
# Scheduler job concurrency controls
SCHEDULER_MAX_INSTANCES = int(os.getenv("SCHEDULER_MAX_INSTANCES", "1"))
SCHEDULER_COALESCE = _str2bool(os.getenv("SCHEDULER_COALESCE", "1"), True)
SCHEDULER_MISFIRE_GRACE_TIME = int(os.getenv("SCHEDULER_MISFIRE_GRACE_TIME", "300"))

# Optional distributed locking with Redis (future use)
SCHEDULER_USE_DISTRIBUTED_LOCK = _str2bool(os.getenv("SCHEDULER_USE_DISTRIBUTED_LOCK", "0"), False)
REDIS_URL: Optional[str] = os.getenv("REDIS_URL")

# Encouragement (daily shared) settings
ENCOURAGEMENT_ENABLED = _str2bool(os.getenv("ENCOURAGEMENT_ENABLED", "1"), True)
ENCOURAGEMENT_CACHE_DAYS = int(os.getenv("ENCOURAGEMENT_CACHE_DAYS", "7"))
ENCOURAGEMENT_MAX_TOKENS = int(os.getenv("ENCOURAGEMENT_MAX_TOKENS", "120"))

# Optional comma-separated company blocklist (case-insensitive). Useful for filtering companies
# which produce malformed or inconsistent job data, e.g. 'MARINA BAY SANDS'
COMPANY_BLOCKLIST = [name.strip() for name in os.getenv("COMPANY_BLOCKLIST", "MARINA BAY SANDS PTE. LTD.").split(',') if name.strip()]
