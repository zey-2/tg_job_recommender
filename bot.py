"""Telegram bot handlers and commands."""
import json
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from bs4 import BeautifulSoup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from telegram.constants import ParseMode
import config
from database import get_db
from findsgjobs_client import get_findsgjobs_client
from keyword_manager import get_keyword_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_SEARCH_QUERY, WAITING_FOR_TIME, WAITING_FOR_MANUAL_KEYWORD, WAITING_FOR_MIN_SALARY = range(4)


class JobBot:
    """Telegram Job Bot."""
    
    def __init__(self):
        """Initialize bot."""
        self.db = get_db()
        self.findsgjobs = get_findsgjobs_client()
        self.keyword_manager = get_keyword_manager()
        # Clear existing negative keywords from DB on startup (migration)
        try:
            self.db.clear_all_negative_keywords()
        except Exception:
            logger.exception("Failed to clear existing negative keywords on startup")
    
    def format_job_message(self, job: dict, explanation: str = None) -> str:
        """Format job as Telegram message."""
        title = job.get('title', 'Unknown')
        company = job.get('company', {})
        if isinstance(company, dict):
            company = company.get('display_name', 'Unknown')
        
        location = job.get('location', {})
        if isinstance(location, dict):
            location = location.get('display_name', 'Singapore')

        # Parse HTML description and preserve line breaks
        raw_desc = job.get('description') or ''
        description = ''
        if raw_desc:
            soup = BeautifulSoup(raw_desc, 'html.parser')
            plain = soup.get_text(separator='\n', strip=True)
            if plain:
                description = (plain[:200] + '...') if len(plain) > 200 else plain
        
        # Salary info
        salary_min = job.get('salary_min')
        salary_max = job.get('salary_max')
        salary_str = ""
        if salary_min and salary_max:
            salary_str = f"\n💰 ${salary_min:,.0f} - ${salary_max:,.0f}"
        elif salary_min:
            salary_str = f"\n💰 From ${salary_min:,.0f}"
        
        message = f"*{title}*\n"
        message += f"🏢 {company}\n"
        # message += f"📍 {location}"
        message += salary_str
        
        if description:
            message += f"\n\n{description}"
        
        if explanation:
            message += f"\n\n💡 _{explanation}_"
        # Additional details: categories, employment, MRT, skills (abbreviated)
        # We append as a footer to the message
        # Categories and employment types
        categories = json.loads(job.get('category_json') or '[]')
        employment_types = json.loads(job.get('employment_type_json') or '[]')
        if categories:
            message += f"\n\n📂 {', '.join(categories[:2])}"
        if employment_types or job.get('work_arrangement'):
            et = ', '.join(employment_types[:2]) if employment_types else ''
            wa = f" • {job.get('work_arrangement')}" if job.get('work_arrangement') else ''
            message += f"\n💼 {et}{wa}"
        # MRT stations
        mrt = json.loads(job.get('mrt_stations_json') or '[]')
        if mrt:
            part = ', '.join(mrt[:3])
            if len(mrt) > 3:
                part += f" +{len(mrt) - 3} more"
            message += f"\n🚇 {part}"
        # Experience/Education
        exp = job.get('experience_required')
        edu = job.get('education_required')
        if exp or edu:
            parts = []
            if exp:
                parts.append(f"Exp: {exp}")
            if edu:
                parts.append(f"Edu: {edu}")
            message += f"\n📋 {' • '.join(parts)}"
        # Skills
        skills = json.loads(job.get('skills_json') or '[]')
        if skills:
            s_text = ', '.join(skills[:5])
            if len(skills) > 5:
                s_text += f" +{len(skills)-5} more"
            message += f"\n🔧 {s_text}"
        return message
    
    def create_job_keyboard(self, job_id: str) -> InlineKeyboardMarkup:
        """Create inline keyboard for job."""
        # Prefer stored 'url' in DB if available
        job_url = None
        try:
            j = self.db.get_job(job_id)
            if j and j.get('url'):
                job_url = j.get('url')
        except Exception:
            job_url = None
        if not job_url:
            job_url = f"https://www.findsgjobs.com/job/{job_id}"

        keyboard = [
            [
                InlineKeyboardButton("👍 Like", callback_data=f"like:{job_id}"),
            ],
            [
                InlineKeyboardButton("🔗 View Job", url=job_url),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        
        # Register user if new
        existing = self.db.get_user(user.id)
        if not existing:
            self.db.create_user(user.id, user.username)
        
        welcome_msg = (
            f"👋 Welcome to Job Bot, {user.first_name}!\n\n"
            "I'll help you find personalized job recommendations based on your preferences.\n\n"
            "<b>How it works:</b>\n"
            "• Use /search or just type keywords to find specific jobs\n"
            "• Like 👍 each job to help refine recommendations\n"
            "• I'll learn what you like and improve over time!\n\n"
            "• Use /more - Get more personalized recommendations\n"
            "📢 <b>Notifications:</b> Daily digest notifications are enabled by default. Use /toggle_notifications to turn them off.\n\n"
            "• Each digest may include a short, positive encouragement message and lucky number to brighten your day."
        )

        
        await update.message.reply_text(welcome_msg, parse_mode=ParseMode.HTML)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "🤖 <b>Job Bot Commands</b>\n\n"
            "📋 <b>Job Discovery:</b>\n"
            "/more - Get 2-3 personalized recommendations\n"
            "/search - Search for specific jobs\n\n"
            "⚙️ <b>Profile &amp; Settings:</b>\n"
            "/view_keywords - View your adaptive keywords\n"
            "/add_keyword - Add a manual keyword (positive only)\n"
            "/keyword_management - Manage and remove keywords (delete, clear)\n"
            "/set_time - Set daily notification time (30-min slots)\n"
            "/toggle_notifications - Turn daily digest on/off\n\n"
            "✨ <b>Daily Encouragements:</b> Each digest may include a short positive message generated to brighten your day.\n\n"
            "❓ <b>Other:</b>\n"
            "/help - Show this help message\n"
            "/start - Reset welcome message\n\n"
            "💡 <b>Tip:</b> Type keywords or use /search to find jobs. Like 👍 jobs to improve recommendations!"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    async def more_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /more command - get real-time recommendations."""
        user_id = update.effective_user.id
        logger.info(f"[MORE] User {user_id} requested more jobs")
        
        # Ensure user exists
        if not self.db.get_user(user_id):
            logger.warning(f"[MORE] User {user_id} not registered")
            await update.message.reply_text(
                "Please use /start first to register!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        await update.message.reply_text("🔍 Finding jobs for you...")
        
        # Get user keywords
        keywords = self.db.get_user_keywords(user_id, top_k=config.TOP_K)
        keyword_list = [kw['keyword'] for kw in keywords if not kw['is_negative']]
        logger.info(f"[MORE] User {user_id} has {len(keywords)} total keywords, {len(keyword_list)} positive: {keyword_list}")
        
        # Pick a random preferred keyword to try first (if any) and attempt search with retries
        preferred_keyword = random.choice(keyword_list) if keyword_list else None
        jobs, used_keyword, deleted_keywords, manual_failed, used_recent = self.keyword_manager.search_with_keyword_retry(
            user_id=user_id, findsg_client=self.findsgjobs, context=context, limit=100, preferred_keyword=preferred_keyword
        )

        # Inform user about keyword deletions or manual failures
        if deleted_keywords:
            await update.message.reply_text(
                f"🔄 Removed keyword(s) with no results: {', '.join(deleted_keywords)}. Trying alternatives...",
                parse_mode=ParseMode.MARKDOWN
            )
        if manual_failed:
            await update.message.reply_text(
                f"⚠️ Your manual keyword(s) returned no results and were kept: {', '.join(manual_failed)}",
                parse_mode=ParseMode.MARKDOWN
            )

        # Inform which source is used
        if used_keyword:
            logger.info(f"[MORE] Using keyword: {used_keyword}")
            await update.message.reply_text(f"🔍 Searching with keyword: *{used_keyword}*", parse_mode=ParseMode.MARKDOWN)
        elif used_recent:
            logger.info(f"[MORE] No usable keywords, fetching recent jobs")
            await update.message.reply_text("🔍 Searching recent jobs (no keywords available or after retries)", parse_mode=ParseMode.MARKDOWN)
        
        logger.info(f"[MORE] Fetched {len(jobs)} jobs from FindSGJobs")
        
        if not jobs:
            logger.warning(f"[MORE] No jobs returned from FindSGJobs for user {user_id} after retries")
            await update.message.reply_text(
                "😕 No jobs found right now. Try again later or use /search to find specific jobs.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Rank jobs
        logger.info(f"[MORE] Ranking {len(jobs)} jobs for user {user_id}")
        ranked = self.keyword_manager.rank_jobs(jobs, user_id, exclude_recent=True)
        logger.info(f"[MORE] After ranking and filtering, {len(ranked)} jobs remain")
        
        if not ranked:
            logger.warning(f"[MORE] No jobs left after ranking/filtering for user {user_id}")
            await update.message.reply_text(
                "You've seen all recent matches! Try /search or check back later.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Send top 2-3 jobs
        count = min(len(ranked), config.REALTIME_MAX)
        logger.info(f"[MORE] Sending {count} jobs to user {user_id}")
        
        for idx, (job, score, matched) in enumerate(ranked[:count], 1):
            # Cache job in database
            self.db.upsert_job(job)
            job_id = job.get('id')
            
            logger.info(f"[MORE] Job {idx}/{count}: {job_id} - {job.get('title')} - Score: {score:.2f}")
            
            # Log as shown
            self.db.log_interaction(user_id, job_id, 'shown')
            
            # Format and send (do not include raw numeric score; show matched keywords only)
            explanation = f"Matched: {', '.join(matched[:3])}" if matched else None
            
            message = self.format_job_message(job, explanation)
            keyboard = self.create_job_keyboard(job_id)
            
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )

    async def digest_now(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a one-off digest to the calling user for testing."""
        user_id = update.effective_user.id
        logger.info(f"[DIGEST_NOW] User {user_id} requested an immediate digest")

        # Ensure user exists
        if not self.db.get_user(user_id):
            await update.message.reply_text("Please use /start first to register!", parse_mode=ParseMode.MARKDOWN)
            return

        # Get user's keywords to pick a preferred one
        keywords = self.db.get_user_keywords(user_id, top_k=config.TOP_K)
        keyword_list = [kw['keyword'] for kw in keywords if not kw['is_negative']]
        logger.info(f"[DIGEST_NOW] User {user_id} has {len(keywords)} total keywords, {len(keyword_list)} positive: {keyword_list}")

        # Reuse the logic from more_command but show DAILY_COUNT jobs with retry/deletion
        # For digest_now: pick a random preferred keyword and attempt search with retries
        preferred_keyword = random.choice(keyword_list) if keyword_list else None
        jobs, used_keyword, deleted_keywords, manual_failed, used_recent = self.keyword_manager.search_with_keyword_retry(
            user_id=user_id, findsg_client=self.findsgjobs, context=context, limit=100, preferred_keyword=preferred_keyword
        )

        # Inform user about keyword deletions or manual failures
        if deleted_keywords:
            await update.message.reply_text(
                f"🔄 Removed keyword(s) with no results: {', '.join(deleted_keywords)}. Trying alternatives...",
                parse_mode=ParseMode.MARKDOWN
            )
        if manual_failed:
            await update.message.reply_text(
                f"⚠️ Your manual keyword(s) returned no results and were kept: {', '.join(manual_failed)}",
                parse_mode=ParseMode.MARKDOWN
            )
        if used_keyword:
            await update.message.reply_text(f"🔍 Searching with keyword: *{used_keyword}*", parse_mode=ParseMode.MARKDOWN)
        elif used_recent:
            await update.message.reply_text("🔍 Searching recent jobs (no keywords available or after retries)", parse_mode=ParseMode.MARKDOWN)

        ranked = self.keyword_manager.rank_jobs(jobs, user_id, exclude_recent=True)
        if not ranked:
            await update.message.reply_text("No new jobs found at the moment. Try again later.")
            return

        header = "📬 *Your Immediate Job Digest*\nHere are your top matches:\n"
        await update.message.reply_text(header, parse_mode=ParseMode.MARKDOWN)

        count = min(len(ranked), config.DAILY_COUNT)
        for job, score, matched in ranked[:count]:
            try:
                self.db.upsert_job(job)
            except Exception as e:
                logger.warning(f"Failed to upsert job {job.get('id')}: {e}")
            job_id = job.get('id')
            self.db.log_interaction(user_id, job_id, 'shown')
            explanation = f"Matched: {', '.join(matched[:3])}" if matched else None
            message = self.format_job_message(job, explanation)
            keyboard = self.create_job_keyboard(job_id)
            try:
                await update.message.reply_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.warning(f"Failed to send digest message to user {user_id}: {e}")
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command - start search conversation."""
        await update.message.reply_text(
            "🔍 *Search for Jobs*\n\n"
            "Please send me the keywords you want to search for.\n\n"
            "Example: `pastry`\n"
            "Example: `delivery`\n\n"
            "Send /cancel to cancel the search.",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_SEARCH_QUERY
    
    async def process_search_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process the search query from user."""
        user_id = update.effective_user.id
        query = update.message.text.strip()
        
        if not query:
            await update.message.reply_text(
                "❌ Please provide search keywords or send /cancel to cancel.",
                parse_mode=ParseMode.MARKDOWN
            )
            return WAITING_FOR_SEARCH_QUERY
        
        await update.message.reply_text(f"🔍 Searching for: *{query}*...", parse_mode=ParseMode.MARKDOWN)
        
        # Search jobs
        jobs = self.findsgjobs.search_custom(query, limit=25, user_id=user_id, context=context)
        
        if not jobs:
            await update.message.reply_text(
                f"😕 No jobs found for '{query}'. Try different keywords.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Auto-add search term as manual keyword if list not full and keyword doesn't exist
        keyword_added = False
        normalized_query = query.lower()
        if len(normalized_query) >= 2 and len(normalized_query) <= 60:
            # Check if manual keyword list is full
            manual_count = self.db.count_manual_keywords(user_id, positive_only=True)
            if manual_count < config.MAX_MANUAL_KEYWORDS:
                # Check if keyword already exists (any source)
                existing = next(
                    (kw for kw in self.db.get_user_keywords(user_id) if kw['keyword'] == normalized_query),
                    None
                )
                if not existing:
                    # Add as manual keyword with moderate weight
                    self.db.upsert_keyword(
                        user_id=user_id,
                        keyword=normalized_query,
                        weight=1.0,
                        is_negative=False,
                        rationale='Auto-added from search query',
                        source='manual'
                    )
                    keyword_added = True
                    logger.info(f"[SEARCH] Auto-added search term '{normalized_query}' as manual keyword for user {user_id}")
        
        # Send top 5 results
        count = min(len(jobs), 5)
        
        for job in jobs[:count]:
            # Cache job
            try:
                self.db.upsert_job(job)
            except Exception as e:
                logger.warning(f"Failed to upsert job {job.get('id')}: {e}")
                # Continue and still attempt to send the job
            job_id = job.get('id')
            
            # Log interaction
            self.db.log_interaction(user_id, job_id, 'shown')
            
            # Send job
            message = self.format_job_message(job)
            keyboard = self.create_job_keyboard(job_id)
            
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Notify user if keyword was auto-added
        if keyword_added:
            await update.message.reply_text(
                f"✨ Added '*{normalized_query}*' to your profile keywords! Like jobs to refine your recommendations.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return ConversationHandler.END

    async def default_text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle default text input as a direct search query (non-command)."""
        # Reuse search processing flow but don't prompt; treat the text as a query
        logger.info(f"[DEFAULT] User {update.effective_user.id} sent text; treating as search query")
        return await self.process_search_query(update, context)
    
    async def view_keywords_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /view_keywords command - show user profile."""
        user_id = update.effective_user.id
        
        display = self.keyword_manager.get_top_keywords_display(user_id)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧾 Manage Keywords", callback_data="km:menu")]])
        await update.message.reply_text(display, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    async def add_keyword_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start flow to add a manual positive keyword."""
        await update.message.reply_text(
            "✍️ *Add a Manual Keyword*\n\nSend the keyword you want to add (single word or phrase).\n\nExample: `teacher`, `cook`, `pastry`\n\nSend /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_MANUAL_KEYWORD

    async def process_manual_keyword_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        keyword = update.message.text.strip().lower()

        # Basic validation
        if len(keyword) < 2 or len(keyword) > 60:
            await update.message.reply_text("❌ Keyword must be 2-60 characters. Send a different keyword or /cancel.")
            return WAITING_FOR_MANUAL_KEYWORD

        # Check duplicate and manual slot limit
        existing = next((kw for kw in self.db.get_user_keywords(user_id) if kw['keyword'] == keyword), None)
        if existing and existing.get('source') == 'manual':
            await update.message.reply_text(f"✅ Keyword '{keyword}' is already in your manual keywords.")
            return ConversationHandler.END

        manual_count = self.db.count_manual_keywords(user_id, positive_only=True)
        if manual_count >= config.MAX_MANUAL_KEYWORDS:
            await update.message.reply_text(
                f"❌ You've reached the maximum of {config.MAX_MANUAL_KEYWORDS} manual keywords. Remove one before adding more."
            )
            return ConversationHandler.END

        # Add keyword as manual positive (fixed weight)
        self.db.upsert_keyword(user_id=user_id, keyword=keyword, weight=1.0, is_negative=False, rationale='Manually added', source='manual')

        await update.message.reply_text(f"✅ Added manual keyword: *{keyword}*", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    async def keyword_management_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show keyword management menu with inline buttons."""
        user_id = update.effective_user.id
        kb = [
            [InlineKeyboardButton("🗑️ Remove One Keyword", callback_data="km:remove_one")],
            [InlineKeyboardButton("🤖 Clear All Auto Keywords", callback_data="km:clear_auto")],
            [InlineKeyboardButton("✍️ Clear All Manual Keywords", callback_data="km:clear_manual")],
            [InlineKeyboardButton("🧹 Clear All Keywords", callback_data="km:clear_all")],
            [InlineKeyboardButton("🔙 Back", callback_data="km:cancel")]
        ]
        await update.message.reply_text("🧾 *Keyword Management Menu*", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    
    async def set_time_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /set_time command - start time setting conversation."""
        await update.message.reply_text(
            "⏰ *Set Your Notification Time*\n\n"
            "Please send me your preferred notification time in *HH:MM* format.\n"
            "Any minute value is allowed (e.g., 09:00, 09:17, 10:45)\n\n"
            "Examples:\n"
            "• `09:00`\n"
            "• `18:05`\n"
            "• `21:59`\n\n"
            "Send /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_TIME

    async def set_min_salary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /set_min_salary command - supply the amount as a message input.
        For backward compatibility, if an argument is provided (/set_min_salary 3000), process it immediately.
        """
        user_id = update.effective_user.id
        args = context.args
        if args:
            # Backward compatibility: parse immediate argument
            try:
                amount = int(args[0])
                if amount < 0:
                    raise ValueError()
            except Exception:
                await update.message.reply_text("❌ Invalid amount. Please provide a positive integer (SGD) or 0 to clear.")
                return

            if amount == 0:
                self.db.update_user_min_salary(user_id, None)
                await update.message.reply_text("✅ Monthly minimum salary filter cleared.")
                return

            self.db.update_user_min_salary(user_id, amount)
            await update.message.reply_text(f"✅ Minimum monthly salary filter set to ${amount} SGD.")
            return

        # No argument: start conversation to accept the amount via text
        await update.message.reply_text(
            "💸 *Set Minimum Monthly Salary (SGD)*\n\n"
            "Send a whole number amount, e.g., `3000`. Send `0` to clear the value.\n\n"
            "Send /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_MIN_SALARY
    
    async def process_time_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process the time input from user."""
        user_id = update.effective_user.id
        time_str = update.message.text.strip()
        
        # Validate format
        try:
            hour, minute = map(int, time_str.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except:
            await update.message.reply_text(
                "❌ Invalid time format. Please use HH:MM (00-23 for hours, 00-59 for minutes).\n\n"
                "Examples: `09:00`, `09:17`, `18:45`\n\n"
                "Send /cancel to cancel.",
                parse_mode=ParseMode.MARKDOWN
            )
            return WAITING_FOR_TIME
        
        # Update user
        self.db.set_notification_time(user_id, time_str)
        
        await update.message.reply_text(
            f"✅ Daily digest time set to *{time_str}* (Singapore Time)",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    async def process_min_salary_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user's min salary conversation input."""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        try:
            amount = int(text)
            if amount < 0:
                raise ValueError()
        except Exception:
            await update.message.reply_text("❌ Invalid amount. Please send a positive integer (SGD) or 0 to clear.")
            return WAITING_FOR_MIN_SALARY

        if amount == 0:
            self.db.update_user_min_salary(user_id, None)
            await update.message.reply_text("✅ Monthly minimum salary filter cleared.")
            return ConversationHandler.END

        self.db.update_user_min_salary(user_id, amount)
        await update.message.reply_text(f"✅ Minimum monthly salary filter set to ${amount} SGD.")
        return ConversationHandler.END
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command."""
        await update.message.reply_text(
            "❌ Operation cancelled.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    async def toggle_notifications_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /toggle_notifications command."""
        user_id = update.effective_user.id
        
        new_state = self.db.toggle_notifications(user_id)
        # Retrieve current stored time and timezone for the user
        user = self.db.get_user(user_id)
        time_str = None
        tz = config.DEFAULT_TIMEZONE
        if user:
            time_str = user.get('notification_time') or config.DEFAULT_NOTIFICATION_TIME
            tz = user.get('timezone') or config.DEFAULT_TIMEZONE

        if new_state:
            # Ensure next_digest_at is recalculated when enabling notifications
            if time_str:
                try:
                    self.db.set_notification_time(user_id, time_str)
                except Exception:
                    # Best-effort; we don't want toggling to fail due to scheduling issues
                    logger.exception("Could not update next_digest_at for user %s", user_id)

            message = f"✅ Daily digest notifications are now *ON* — scheduled at *{time_str}* ({tz})"
        else:
            # When notifications are turned off, show the current/previous time for reference
            message = f"🔕 Daily digest notifications are now *OFF* (previously set to *{time_str}* {tz})"

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

    async def reset_profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start flow to reset user profile (keywords/interactions)."""
        user_id = update.effective_user.id
        kb = [
            [InlineKeyboardButton("✅ Reset Everything", callback_data="reset:confirm:all"), InlineKeyboardButton("❌ Cancel", callback_data="reset:cancel")],
            [InlineKeyboardButton("🔧 Reset Keywords Only", callback_data="reset:confirm:keywords"), InlineKeyboardButton("📊 Reset History Only", callback_data="reset:confirm:history")]
        ]
        await update.message.reply_text(
            "⚠️ *Reset Profile*\n\nChoose what you'd like to reset:\n• Everything: keywords + history\n• Keywords only: remove manual + auto keywords\n• History only: clear interactions (shown/liked)",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query
        try:
            await query.answer()
        except Exception as e:
            logger.warning(f"Failed to answer callback query (possible timeout): {e}")
            # Continue; user may still see UI update eventually
        
        user_id = update.effective_user.id
        data = query.data
        if not data:
            return

        # Handle keyword management callbacks starting with 'km:'
        # Reset profile callbacks
        if data.startswith('reset:'):
            parts = data.split(':')
            action = parts[1] if len(parts) > 1 else None
            reset_type = parts[2] if len(parts) > 2 else None
            logger.info(f"[RESET] handling action {action} {reset_type} for user {user_id}")
            if action == 'cancel':
                await query.edit_message_text("❌ Reset cancelled.")
                return
            if action == 'confirm':
                if reset_type == 'all':
                    # clear keywords and history, keep notification settings
                    self.db.reset_user_profile(user_id, keep_settings=True)
                    await query.edit_message_text("✅ Profile reset complete! All keywords and history cleared.")
                    return
                if reset_type == 'keywords':
                    self.db.clear_auto_keywords(user_id)
                    self.db.clear_manual_keywords(user_id)
                    await query.edit_message_text("✅ All keywords cleared!")
                    return
                if reset_type == 'history':
                    self.db.clear_user_interactions(user_id)
                    await query.edit_message_text("✅ Interaction history cleared!")
                    return
                await query.edit_message_text("❌ Unknown reset type.")
                return
        if data.startswith('km:'):
            parts = data.split(':')
            cmd = parts[1] if len(parts) > 1 else None
            logger.info(f"[KM] handling cmd {cmd} for user {user_id}")
            if cmd == 'menu' or cmd == 'cancel':
                kb = [
                    [InlineKeyboardButton("🗑️ Remove One Keyword", callback_data="km:remove_one")],
                    [InlineKeyboardButton("🤖 Clear All Auto Keywords", callback_data="km:clear_auto")],
                    [InlineKeyboardButton("✍️ Clear All Manual Keywords", callback_data="km:clear_manual")],
                    [InlineKeyboardButton("🧹 Clear All Keywords", callback_data="km:clear_all")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="km:cancel")]
                ]
                await query.edit_message_text("🧾 Keyword Management Menu", reply_markup=InlineKeyboardMarkup(kb))
                return
            if cmd == 'remove_one':
                kws = self.db.get_user_keywords(user_id)
                if not kws:
                    await query.edit_message_text("You have no keywords.")
                    return
                kb = []
                for kw in kws:
                    source = kw.get('source') or 'auto'
                    emoji = '✍️' if source == 'manual' else '🤖'
                    kb.append([InlineKeyboardButton(f"{emoji} {kw['keyword']}", callback_data=f"km:del:{kw['id']}")])
                kb.append([InlineKeyboardButton("🔙 Back to menu", callback_data="km:menu")])
                await query.edit_message_text("Select a keyword to remove:", reply_markup=InlineKeyboardMarkup(kb))
                return
            if cmd == 'del' and len(parts) > 2:
                kid = parts[2]
                kw = self.db.get_keyword_by_id(user_id, int(kid))
                if not kw:
                    await query.edit_message_text("Keyword not found.")
                    return
                kb = [
                    [InlineKeyboardButton("✅ Yes, delete", callback_data=f"km:del_confirm:{kid}"), InlineKeyboardButton("🔙 Back", callback_data="km:menu")]
                ]
                await query.edit_message_text(f"⚠️ Delete keyword: *{kw['keyword']}*?", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
                return
            if cmd == 'del_confirm' and len(parts) > 2:
                kid = parts[2]
                kw = self.db.get_keyword_by_id(user_id, int(kid))
                if not kw:
                    await query.edit_message_text("Keyword not found.")
                    return
                self.db.delete_keyword_by_id(user_id, int(kid))
                await query.edit_message_text(f"✅ Deleted keyword: {kw['keyword']}")
                return
            if cmd == 'clear_auto':
                kb = [[InlineKeyboardButton("✅ Yes, clear auto keywords", callback_data="km:clear_auto_confirm"), InlineKeyboardButton("🔙 Back", callback_data="km:menu")]]
                await query.edit_message_text("⚠️ Delete ALL auto-generated keywords?", reply_markup=InlineKeyboardMarkup(kb))
                return
            if cmd == 'clear_auto_confirm':
                self.db.clear_auto_keywords(user_id)
                await query.edit_message_text("✅ Cleared auto-generated keywords.")
                return
            if cmd == 'clear_manual':
                kb = [[InlineKeyboardButton("✅ Yes, clear manual keywords", callback_data="km:clear_manual_confirm"), InlineKeyboardButton("🔙 Back", callback_data="km:menu")]]
                await query.edit_message_text("⚠️ Delete ALL manual keywords?", reply_markup=InlineKeyboardMarkup(kb))
                return
            if cmd == 'clear_manual_confirm':
                self.db.clear_manual_keywords(user_id)
                await query.edit_message_text("✅ Cleared manual keywords.")
                return
            if cmd == 'clear_all':
                kb = [[InlineKeyboardButton("✅ Yes, clear all keywords", callback_data="km:clear_all_confirm"), InlineKeyboardButton("🔙 Back", callback_data="km:menu")]]
                await query.edit_message_text("⚠️ Delete ALL keywords (manual + auto)?", reply_markup=InlineKeyboardMarkup(kb))
                return
            if cmd == 'clear_all_confirm':
                self.db.clear_auto_keywords(user_id)
                self.db.clear_manual_keywords(user_id)
                await query.edit_message_text("✅ Cleared all keywords.")
                return
            await query.edit_message_text("Unknown keyword management command.")
            return

        # Parse like/dislike callback data
        if ':' not in data:
            return
        action, job_id = data.split(':', 1)
        if action not in ['like', 'dislike']:
            return
        
        # Show processing message
        processing_text = "⏳ Processing your feedback..."
        try:
            await query.edit_message_text(
                processing_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.warning(f"Could not show processing message: {e}")
        
        # Get job from database
        job = self.db.get_job(job_id)
        if not job:
            await query.edit_message_text(
                "❌ Job not found in database.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Log interaction
        self.db.log_interaction(user_id, job_id, action)
        
        # Update keywords based on feedback
        self.keyword_manager.update_keywords_from_feedback(user_id, job, action)
        
        # Update message
        emoji = "👍" if action == 'like' else "👎"
        feedback_msg = f"\n\n{emoji} *{action.capitalize()}d!* Your profile has been updated."
        
        try:
            await query.edit_message_text(
                query.message.text + feedback_msg,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            # Message might be too old to edit
            await query.message.reply_text(
                f"{emoji} Job {action}d! Your profile has been updated.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def create_application(self, start_scheduler: bool = False) -> Application:
        """Create and configure the bot application."""
        
        async def set_commands(application):
            """Set bot commands after initialization."""
            commands = [
                BotCommand("start", "Start the bot and get welcome message"),
                BotCommand("more", "Get personalized job recommendations"),
                BotCommand("search", "Search for jobs with specific keywords"),
                BotCommand("view_keywords", "View your keyword profile"),
                BotCommand("add_keyword", "Add a manual keyword to your profile"),
                BotCommand("keyword_management", "Manage and remove keywords"),
                BotCommand("set_time", "Set daily notification time"),
                BotCommand("set_min_salary", "Set minimum monthly salary filter (SGD)"),
                BotCommand("toggle_notifications", "Turn daily digest on/off"),
                BotCommand("digest_now", "Receive an immediate digest (testing)"),
                BotCommand("reset_profile", "Reset your profile (keywords/history)"),
                BotCommand("help", "Show help and available commands"),
            ]
            await application.bot.set_my_commands(commands)
        
        async def _post_init(application):
            # set commands as before
            await set_commands(application)
            # optionally start scheduler
            if start_scheduler and config.SCHEDULER_ENABLED:
                # Start scheduler in the running event loop
                from scheduler import start_background_scheduler
                start_background_scheduler(application)

        application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(_post_init).build()
        
        # Conversation handler for /search
        search_handler = ConversationHandler(
            entry_points=[CommandHandler("search", self.search_command)],
            states={
                WAITING_FOR_SEARCH_QUERY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_search_query)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )
        
        # Conversation handler for /set_time
        set_time_handler = ConversationHandler(
            entry_points=[CommandHandler("set_time", self.set_time_command)],
            states={
                WAITING_FOR_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_time_input)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )

        # Conversation handler for /set_min_salary (similar to /set_time)
        set_min_salary_handler = ConversationHandler(
            entry_points=[CommandHandler("set_min_salary", self.set_min_salary)],
            states={
                WAITING_FOR_MIN_SALARY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_min_salary_input)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )
        
        # Add conversation handlers
        application.add_handler(search_handler)
        application.add_handler(set_time_handler)
        application.add_handler(set_min_salary_handler)
        # Add manual keyword handler
        add_keyword_handler = ConversationHandler(
            entry_points=[CommandHandler("add_keyword", self.add_keyword_command)],
            states={
                WAITING_FOR_MANUAL_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_manual_keyword_input)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)],
        )
        application.add_handler(add_keyword_handler)
        
        # Other command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("more", self.more_command))
        application.add_handler(CommandHandler("view_keywords", self.view_keywords_command))
        # `set_min_salary` is handled by a ConversationHandler (set_min_salary_handler) above
        application.add_handler(CommandHandler("digest_now", self.digest_now))
        application.add_handler(CommandHandler("reset_profile", self.reset_profile_command))
        # `add_keyword` is registered as a ConversationHandler; don't add a plain command handler here to avoid duplicate handling.
        application.add_handler(CommandHandler("keyword_management", self.keyword_management_command))
        application.add_handler(CommandHandler("toggle_notifications", self.toggle_notifications_command))
        application.add_handler(CommandHandler("help", self.help_command))
        # Default text handler should be registered after conversation handlers so it doesn't interfere
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.default_text_handler))
        
        # Callback handler for inline buttons
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        return application


# Global bot instance
_bot = None

def get_bot() -> JobBot:
    """Get global bot instance."""
    global _bot
    if _bot is None:
        _bot = JobBot()
    return _bot
