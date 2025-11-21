# Telegram Job Recommendation Bot

An intelligent Telegram bot that delivers personalized job notifications using adaptive keyword learning with LLM integration.

## Features

- 🧠 **Adaptive User Profiling**: Learns from your likes/dislikes
- 🤖 **LLM Keyword Expansion**: Uses OpenAI to extract relevant keywords
- 📈 **Smart Job Scoring**: Ranks jobs based on your preferences
- 🔔 **Daily Digest**: Scheduled notifications at your preferred time
- 💬 **Interactive Commands**: Easy-to-use Telegram interface
- 💪 **Daily Encouragement**: Optional AI-generated motivational messages with each digest
- 🎲 **Lucky Numbers**: Personalized lucky number calculated from encouragement message, user ID, and day of month
- 💰 **Salary Filtering**: Set minimum salary threshold to filter job recommendations
- 🔄 **Profile Reset**: Clear your profile and start fresh when needed

## Introductory Video

[![Introductory Video](https://img.youtube.com/vi/ShDbWd0dFgA/0.jpg)](https://youtu.be/ShDbWd0dFgA)

## Link to Telegram Bot

[![Telegram Bot](https://img.shields.io/badge/Telegram-Job%20Recommender-blue?logo=telegram)](https://t.me/sg_jobs_radar_bot)

## Setup

### 1. Install Dependencies

Using pip:

```bash
pip install -r requirements.txt
```

Or using conda:

```bash
conda install --file requirements.txt
conda activate telegram-job-bot
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required credentials:

- **TELEGRAM_BOT_TOKEN**: Get from [@BotFather](https://t.me/botfather)
  -- **FINDSGJOBS_API_ENDPOINT**: FindSGJobs endpoint URL (https://www.findsgjobs.com/apis/job/searchable)
- **OPENAI_API_KEY**: Get from [OpenAI Platform](https://platform.openai.com/)

### 3. Run the Bot

**Development (Polling Mode):**

```bash
python main.py
```

**Production (Polling Mode — self-scheduling):**
Run the bot in polling mode; a background scheduler will run every minute to send digests:

```bash
python main.py
```

**Run Digest Job:**

```bash
python main.py digest
```

## Available Commands

### Job Discovery

- `/start` - Register and get welcome message
- `/more` - Get 2-3 personalized job recommendations
- `/search <keywords>` - Search for specific jobs
- `/digest_now` - Receive an immediate digest (testing)

### Profile & Keywords

- `/view_keywords` - View your adaptive keyword profile
- `/add_keyword` - Add a manual positive keyword to your profile (max 4)
- `/keyword_management` - Manage and remove keywords (delete one, clear auto/manual/all with confirmation)
- `/reset_profile` - Reset your profile (keywords and interaction history)

### Settings

- `/set_time <HH:MM>` - Set daily notification time (30-min slots, Singapore Time)
- `/set_min_salary` - Set minimum monthly salary filter (SGD)
- `/toggle_notifications` - Turn daily digest on/off

### Help

- `/help` - Show help message with all commands

## Project Structure

```
tg_job_recommender/
├── main.py                 # Entry point
├── bot.py                  # Telegram bot handlers
├── config.py               # Configuration
├── database.py             # SQLite database operations
├── findsgjobs_client.py    # FindSGJobs API client
├── keyword_manager.py      # Keyword scoring logic
├── llm_service.py          # OpenAI integration
├── scheduler.py            # Daily digest scheduler
├── requirements.txt        # Dependencies
├── .env.example            # Environment template
└── README.md              # This file
```

## How It Works

1. **User Interaction**: User likes/dislikes jobs via Telegram
2. **LLM Analysis**: OpenAI extracts keywords from job details
3. **Profile Update**: Keywords that appeared in the job are immediately reinforced/penalized, then the LLM suggests new terms
4. **Job Scoring**: Future jobs are ranked by keyword match
5. **Adaptive Learning**: Weights decay over time to stay current
6. **Manual Keywords**: Users can add up to 3 manual positive keywords; these are considered fixed (no decay) and cannot be overwritten by automatically generated keywords. Auto keywords are capped at 5, keeping a clean 3 manual + 5 auto policy
7. **Daily Encouragement**: Each digest optionally includes an AI-generated motivational message
8. **Lucky Number**: When encouragement is enabled, a personalized lucky number (0-9999) is calculated using ASCII sum of the encouragement text + (user_id × day_of_month) mod 10000

## Deployment

The bot is designed to run as a long-running polling service. For production deployment:

1. **Use a persistent hosting service** (VPS, dedicated server, or platform with always-on containers)
2. **Run in polling mode**: `python main.py` (default mode)
3. **Enable background scheduler**: The bot includes an in-process scheduler that checks every minute for users due for digest delivery
4. **Set environment variables**: Ensure all required credentials are configured

## Environment Variables

| Variable                        | Description                                                        | Default        |
| ------------------------------- | ------------------------------------------------------------------ | -------------- |
| `TELEGRAM_BOT_TOKEN`            | Telegram bot token                                                 | Required       |
| `FINDSGJOBS_API_ENDPOINT`       | FindSGJobs API endpoint (search or searchable)                     | Required       |
| `OPENAI_API_KEY`                | OpenAI API key                                                     | Required       |
| `TOP_K`                         | Max adaptive keywords                                              | 8              |
| `DAILY_COUNT`                   | Jobs per daily digest                                              | 5              |
| `DECAY`                         | Weight decay factor                                                | 0.98           |
| `LIKE_BOOST`                    | Weight increase on like                                            | 1.0            |
| `DISLIKE_PENALTY`               | Weight decrease on dislike                                         | -1.0           |
| `MAX_NEW_POSITIVE_PER_FEEDBACK` | New positive keywords allowed per feedback once you already have 8 | 3              |
| `MAX_NEW_NEGATIVE_PER_FEEDBACK` | New negative keywords allowed per feedback cycle                   | 2              |
| `SCHEDULER_ENABLED`             | Enable in-process scheduler (polling mode)                         | true           |
| `SCHEDULER_INTERVAL_SECONDS`    | Scheduler interval in seconds for digest checks                    | 60             |
| `SCHEDULER_TZ`                  | Scheduler timezone                                                 | Asia/Singapore |
| `DEFAULT_TIMEZONE`              | Default timezone for users and lucky number calculation            | Asia/Singapore |
| `ENCOURAGEMENT_MAX_TOKENS`      | Max tokens for LLM-generated encouragement messages                | 50             |
| `MIN_SALARY_DEFAULT`            | Default minimum salary filter (SGD), 0 = no filter                 | 0              |

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
