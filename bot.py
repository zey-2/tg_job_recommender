"""Telegram bot handlers and commands."""
import json
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, ConversationHandler
)
from telegram.constants import ParseMode
import config
from database import get_db
from adzuna_client import get_adzuna_client
from keyword_manager import get_keyword_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_SEARCH_QUERY, WAITING_FOR_TIME = range(2)


class JobBot:
    """Telegram Job Bot."""
    
    def __init__(self):
        """Initialize bot."""
        self.db = get_db()
        self.adzuna = get_adzuna_client()
        self.keyword_manager = get_keyword_manager()
    
    def format_job_message(self, job: dict, explanation: str = None) -> str:
        """Format job as Telegram message."""
        title = job.get('title', 'Unknown')
        company = job.get('company', {})
        if isinstance(company, dict):
            company = company.get('display_name', 'Unknown')
        
        location = job.get('location', {})
        if isinstance(location, dict):
            location = location.get('display_name', 'Singapore')
        
        description = job.get('description', '')[:300]
        if description:
            description = description.replace('\n', ' ').strip()
            if len(job.get('description', '')) > 300:
                description += '...'
        
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
        message += f"📍 {location}"
        message += salary_str
        
        if description:
            message += f"\n\n{description}"
        
        if explanation:
            message += f"\n\n💡 _{explanation}_"
        
        return message
    
    def create_job_keyboard(self, job_id: str) -> InlineKeyboardMarkup:
        """Create inline keyboard for job."""
        keyboard = [
            [
                InlineKeyboardButton("👍 Like", callback_data=f"like:{job_id}"),
                InlineKeyboardButton("👎 Dislike", callback_data=f"dislike:{job_id}"),
            ],
            [
                InlineKeyboardButton("🔗 View Job", url=f"https://www.adzuna.sg/details/{job_id}"),
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
            "• Use /search to find specific jobs\n"
            "• Like 👍 or dislike 👎 each job to help refine recommendations\n"
            "• I'll learn what you like and improve over time!\n\n"
            "📢 <b>Notifications:</b> Daily digest notifications are enabled by default. Use /toggle_notifications to turn them off.\n\n"
            "📝 <b>Available Commands:</b>\n"
            "/more - Get 2-3 personalized recommendations (use multiple times)\n"
            "/search - Search for specific jobs\n"
            "/keywords - View your keyword profile\n"
            "/set_time - Set notification time\n"
            "/toggle_notifications - Turn daily digest on/off\n"
            "/help - Show this help message"
        )

        
        await update.message.reply_text(welcome_msg, parse_mode=ParseMode.HTML)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = (
            "🤖 *Job Bot Commands*\n\n"
            "📋 *Job Discovery:*\n"
            "/more - Get 2-3 personalized recommendations\n"
            "/search - Search for specific jobs\n\n"
            "⚙️ *Profile & Settings:*\n"
            "/keywords - View your adaptive keywords\n"
            "/set_time - Set daily notification time (30-min slots)\n"
            "/toggle_notifications - Turn daily digest on/off\n\n"
            "❓ *Other:*\n"
            "/help - Show this help message\n"
            "/start - Reset welcome message\n\n"
            "💡 *Tip:* Like and dislike jobs to improve recommendations!"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
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
        
        # Randomly select 1 keyword for search (if available)
        if len(keyword_list) >= 1:
            selected_keywords = random.sample(keyword_list, 1)
        else:
            selected_keywords = []
        
        logger.info(f"[MORE] Selected keywords for search: {selected_keywords}")
        
        # Display the keyword being used
        if selected_keywords:
            await update.message.reply_text(f"🔍 Searching with keyword: *{selected_keywords[0]}*", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("🔍 Searching recent jobs (no keywords available yet)", parse_mode=ParseMode.MARKDOWN)
        
        # Fetch jobs
        if selected_keywords:
            logger.info(f"[MORE] Searching by keywords: {selected_keywords}")
            jobs = self.adzuna.search_by_keywords(selected_keywords, limit=50)
        else:
            logger.info(f"[MORE] No keywords found, fetching recent jobs")
            jobs = self.adzuna.get_recent_jobs(limit=50)
        
        logger.info(f"[MORE] Fetched {len(jobs)} jobs from Adzuna")
        
        if not jobs:
            logger.warning(f"[MORE] No jobs returned from Adzuna for user {user_id}")
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
            
            # Format and send
            explanation = f"Match score: {score:.1f}"
            if matched:
                explanation += f" • Matched: {', '.join(matched[:3])}"
            
            message = self.format_job_message(job, explanation)
            keyboard = self.create_job_keyboard(job_id)
            
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command - start search conversation."""
        await update.message.reply_text(
            "🔍 *Search for Jobs*\n\n"
            "Please send me the keywords you want to search for.\n\n"
            "Example: `data analyst python`\n"
            "Example: `software engineer java`\n\n"
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
        jobs = self.adzuna.search_custom(query, limit=25)
        
        if not jobs:
            await update.message.reply_text(
                f"😕 No jobs found for '{query}'. Try different keywords.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # Send top 5 results
        count = min(len(jobs), 5)
        
        for job in jobs[:count]:
            # Cache job
            self.db.upsert_job(job)
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
        
        return ConversationHandler.END
    
    async def keywords_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /keywords command - show user profile."""
        user_id = update.effective_user.id
        
        display = self.keyword_manager.get_top_keywords_display(user_id)
        await update.message.reply_text(display, parse_mode=ParseMode.MARKDOWN)
    
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
        
        if new_state:
            message = "✅ Daily digest notifications are now *ON*"
        else:
            message = "🔕 Daily digest notifications are now *OFF*"
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        # Parse callback data
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
                BotCommand("keywords", "View your keyword profile"),
                BotCommand("set_time", "Set daily notification time"),
                BotCommand("toggle_notifications", "Turn daily digest on/off"),
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
        
        # Add conversation handlers
        application.add_handler(search_handler)
        application.add_handler(set_time_handler)
        
        # Other command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("more", self.more_command))
        application.add_handler(CommandHandler("keywords", self.keywords_command))
        application.add_handler(CommandHandler("toggle_notifications", self.toggle_notifications_command))
        application.add_handler(CommandHandler("help", self.help_command))
        
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
