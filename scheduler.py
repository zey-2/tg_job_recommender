"""Scheduler for daily digest notifications."""
import asyncio
import logging
from datetime import datetime
from pytz import timezone
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from typing import List, Dict
from telegram import Bot
from telegram.constants import ParseMode
import config
from database import get_db
from findsgjobs_client import get_findsgjobs_client
from keyword_manager import get_keyword_manager
from bot import get_bot
from llm_service import get_llm_service

logger = logging.getLogger(__name__)


class DigestScheduler:
    """Handles daily digest notifications."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.db = get_db()
        self.findsgjobs = get_findsgjobs_client()
        self.keyword_manager = get_keyword_manager()
        self.job_bot = get_bot()
    
    async def send_digest_to_user(self, bot: Bot, user: Dict):
        """Send daily digest to a single user."""
        user_id = user['user_id']
        # Extract optional encouragement message passed via user dict
        encouragement = user.get('encouragement')
        
        try:
            # Get user keywords
            keywords = self.db.get_user_keywords(user_id, top_k=config.TOP_K)
            keyword_list = [kw['keyword'] for kw in keywords if not kw['is_negative']]

            # Randomly select 1 keyword for search (if available)
            if len(keyword_list) >= 1:
                selected_keywords = random.sample(keyword_list, 1)
            else:
                selected_keywords = []

            # Log / print keywords used for this user's digest (helpful for debugging)
            logger.info(f"[DIGEST] User {user_id} has {len(keyword_list)} positive keywords")
            logger.info(f"[DIGEST] User {user_id} selected keyword for search: {selected_keywords}")
            print(f"[DIGEST] User {user_id} has {len(keyword_list)} positive keywords: {keyword_list}")
            print(f"[DIGEST] User {user_id} selected keyword for search: {selected_keywords}")
            
            # Create a lightweight context to enable rate-limit messages
            class _Ctx:
                def __init__(self, bot, chat_id):
                    self.bot = bot
                    self.chat_id = chat_id
                    self._chat_id = chat_id

            ctx = _Ctx(bot, user_id)
            # Fetch jobs using retry logic; for scheduled digests we will perform silent cleanup (log deleted keywords)
            preferred_keyword = random.choice(keyword_list) if keyword_list else None
            jobs, used_keyword, deleted_keywords, manual_failed, used_recent = self.keyword_manager.search_with_keyword_retry(
                user_id=user_id, findsg_client=self.findsgjobs, context=ctx, limit=50, preferred_keyword=preferred_keyword
            )
            if deleted_keywords:
                logger.info(f"[DIGEST] Deleted auto keywords for user {user_id} during digest retry: {deleted_keywords}")
            
            if not jobs:
                # No jobs found - skip for now
                return
            
            # Rank jobs
            ranked = self.keyword_manager.rank_jobs(jobs, user_id, exclude_recent=True)
            
            if not ranked:
                # No new jobs
                return
            
            # Send header (include optional daily encouragement if present)
            header = "📬 *Your Daily Job Digest*\n"
            if encouragement:
                header += f"💪 {encouragement}\n\n"
            header += "Here are your top 5:\n"
            await bot.send_message(
                chat_id=user_id,
                text=header,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send top jobs
            count = min(len(ranked), config.DAILY_COUNT)
            
            for job, score, matched in ranked[:count]:
                # Cache job
                self.db.upsert_job(job)
                job_id = job.get('id')
                
                # Log as shown
                self.db.log_interaction(user_id, job_id, 'shown')
                
                # Format message
                explanation = None
                if matched:
                    explanation = f"Matched: {', '.join(matched[:3])}"
                
                message = self.job_bot.format_job_message(job, explanation)
                keyboard = self.job_bot.create_job_keyboard(job_id)
                
                # Send job
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
            
            # Next digest already advanced by reservation (DB-level update). No action required here.
            
        except Exception as e:
            print(f"Error sending digest to user {user_id}: {e}")
    
    async def run_digest_job(self):
        """Run digest job - send to all eligible users."""
        print("Running daily digest job...")
        
        # Reserve users due for digest atomically and advance their next_digest_at
        now_iso = datetime.now(timezone(config.DEFAULT_TIMEZONE)).isoformat()
        users = self.db.reserve_due_users_for_digest(now_iso)
        
        if not users:
            print("No users due for digest")
            return
        
        print(f"Sending digest to {len(users)} users")
        
        # Create bot instance
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

        # Determine today's encouragement message (single message for all users)
        encouragement_msg = None
        if config.ENCOURAGEMENT_ENABLED:
            today_date = datetime.now(timezone(config.DEFAULT_TIMEZONE)).date().isoformat()
            encouragement_msg = self.db.get_daily_cache('encouragement_message', today_date)
            if not encouragement_msg:
                # Generate new encouragement and cache it
                try:
                    llm = get_llm_service()
                    encouragement_msg = llm.generate_encouragement()
                    if encouragement_msg:
                        self.db.set_daily_cache('encouragement_message', encouragement_msg, today_date)
                except Exception as e:
                    logger.warning("Failed to generate encouragement message: %s", e)
                    encouragement_msg = None
        
        # Send to each user (attach encouragement message to the user payload so send_digest_to_user can read it)
        for user in users:
            user['encouragement'] = encouragement_msg
            await self.send_digest_to_user(bot, user)
            # Delay between users to avoid rate limits
            await asyncio.sleep(1)
        
        print("Digest job completed")


# Global scheduler instance
_scheduler = None
_apscheduler = None

def get_scheduler() -> DigestScheduler:
    """Get global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = DigestScheduler()
    return _scheduler


async def run_digest():
    """Entry point for running digest job."""
    scheduler = get_scheduler()
    await scheduler.run_digest_job()


def start_background_scheduler(application=None):
    """Start a background scheduler (APScheduler AsyncIO) that runs run_digest every interval.

    Returns the scheduler instance.
    """
    logger.info("Starting background scheduler (self-scheduling)")
    global _apscheduler
    scheduler = AsyncIOScheduler(timezone=config.SCHEDULER_TZ)

    # Job listener for logging
    def _job_listener(event):
        if event.code == EVENT_JOB_EXECUTED:
            logger.info("Scheduler job executed successfully")
        elif event.code == EVENT_JOB_ERROR:
            logger.exception("Scheduler job raised an exception")

    scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # Schedule the async run_digest coroutine directly
    scheduler.add_job(
        run_digest,
        trigger="interval",
        seconds=config.SCHEDULER_INTERVAL_SECONDS,
        max_instances=config.SCHEDULER_MAX_INSTANCES,
        coalesce=config.SCHEDULER_COALESCE,
        misfire_grace_time=config.SCHEDULER_MISFIRE_GRACE_TIME,
        id="run_digest_job",
    )

    _apscheduler = scheduler
    scheduler.start()
    logger.info("Background scheduler started")
    # Optionally pre-generate the daily encouragement message at startup to reduce first-request latency
    if config.ENCOURAGEMENT_ENABLED:
        try:
            scheduler_instance = get_scheduler()
            today_date = datetime.now(timezone(config.DEFAULT_TIMEZONE)).date().isoformat()
            cache_value = scheduler_instance.db.get_daily_cache('encouragement_message', today_date)
            if not cache_value:
                llm = get_llm_service()
                msg = llm.generate_encouragement()
                if msg:
                    scheduler_instance.db.set_daily_cache('encouragement_message', msg, today_date)
        except Exception as e:
            logger.warning("Failed to pre-generate encouragement message on startup: %s", e)
    # Cleanup old cached messages to prevent table growth
    try:
        get_scheduler().db.cleanup_old_cache(config.ENCOURAGEMENT_CACHE_DAYS)
    except Exception:
        logger.info("No cache cleanup performed or error occurred")
    return scheduler


def shutdown_scheduler(scheduler):
    """Shutdown the background scheduler if running."""
    global _apscheduler
    if not scheduler:
        scheduler = _apscheduler
    if not scheduler:
        return
    try:
        logger.info("Shutting down background scheduler...")
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler shut down")
    except Exception:
        logger.exception("Error shutting down scheduler")
