"""Scheduler for daily digest notifications."""
import asyncio
from typing import List, Dict
from telegram import Bot
from telegram.constants import ParseMode
import config
from database import get_db
from adzuna_client import get_adzuna_client
from keyword_manager import get_keyword_manager
from bot import get_bot


class DigestScheduler:
    """Handles daily digest notifications."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.db = get_db()
        self.adzuna = get_adzuna_client()
        self.keyword_manager = get_keyword_manager()
        self.job_bot = get_bot()
    
    async def send_digest_to_user(self, bot: Bot, user: Dict):
        """Send daily digest to a single user."""
        user_id = user['user_id']
        
        try:
            # Get user keywords
            keywords = self.db.get_user_keywords(user_id, top_k=config.TOP_K)
            keyword_list = [kw['keyword'] for kw in keywords if not kw['is_negative']]
            
            # Fetch jobs
            if keyword_list:
                jobs = self.adzuna.search_by_keywords(keyword_list, limit=50)
            else:
                jobs = self.adzuna.get_recent_jobs(limit=50)
            
            if not jobs:
                # No jobs found - skip for now
                return
            
            # Rank jobs
            ranked = self.keyword_manager.rank_jobs(jobs, user_id, exclude_recent=True)
            
            if not ranked:
                # No new jobs
                return
            
            # Send header
            header = (
                "📬 *Your Daily Job Digest*\n\n"
                f"Found {len(ranked)} new matches for you!\n"
                "Here are your top 5:\n"
            )
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
            
            # Update next digest time
            self.db.update_next_digest(user_id)
            
        except Exception as e:
            print(f"Error sending digest to user {user_id}: {e}")
    
    async def run_digest_job(self):
        """Run digest job - send to all eligible users."""
        print("Running daily digest job...")
        
        # Get users due for digest
        users = self.db.get_users_for_digest()
        
        if not users:
            print("No users due for digest")
            return
        
        print(f"Sending digest to {len(users)} users")
        
        # Create bot instance
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        
        # Send to each user
        for user in users:
            await self.send_digest_to_user(bot, user)
            # Delay between users to avoid rate limits
            await asyncio.sleep(1)
        
        print("Digest job completed")


# Global scheduler instance
_scheduler = None

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
