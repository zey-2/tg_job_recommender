# Telegram Job Recommendation Bot

An intelligent Telegram bot that delivers personalized job notifications using adaptive keyword learning with LLM integration.

## Features

- 🧠 **Adaptive User Profiling**: Learns from your likes/dislikes
- 🤖 **LLM Keyword Expansion**: Uses OpenAI to extract relevant keywords
- 📈 **Smart Job Scoring**: Ranks jobs based on your preferences
- 🔔 **Daily Digest**: Scheduled notifications at your preferred time
- 💬 **Interactive Commands**: Easy-to-use Telegram interface

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required credentials:
- **TELEGRAM_BOT_TOKEN**: Get from [@BotFather](https://t.me/botfather)
- **ADZUNA_APP_ID** & **ADZUNA_APP_KEY**: Register at [Adzuna Developer](https://developer.adzuna.com/)
- **OPENAI_API_KEY**: Get from [OpenAI Platform](https://platform.openai.com/)

### 3. Run the Bot

**Development (Polling Mode):**
```bash
python main.py
```

**Production (Webhook Mode):**
```bash
python main.py webhook 8080
```

**Run Digest Job:**
```bash
python main.py digest
```

## Available Commands

- `/start` - Register and get welcome message
- `/more` - Get 2-3 personalized job recommendations
- `/search <keywords>` - Search for specific jobs
- `/keywords` - View your adaptive keyword profile
- `/set_time <HH:MM>` - Set daily notification time (30-min slots)
- `/toggle_notifications` - Turn daily digest on/off
- `/help` - Show help message

## Project Structure

```
tg_job_recommender/
├── main.py                 # Entry point
├── bot.py                  # Telegram bot handlers
├── config.py               # Configuration
├── database.py             # SQLite database operations
├── adzuna_client.py        # Adzuna API client
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
3. **Profile Update**: Keywords are weighted based on feedback
4. **Job Scoring**: Future jobs are ranked by keyword match
5. **Adaptive Learning**: Weights decay over time to stay current

## Deployment (Cloud Run)

### Build Docker Image

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "main.py", "webhook", "8080"]
```

### Deploy to Google Cloud Run

```bash
gcloud run deploy telegram-job-bot \
  --source . \
  --platform managed \
  --region asia-southeast1 \
  --allow-unauthenticated
```

### Set Up Cloud Scheduler

Create a job that hits `/digest-cron` every 30 minutes:

```bash
gcloud scheduler jobs create http digest-job \
  --schedule="*/30 * * * *" \
  --uri="https://your-cloud-run-url/digest-cron" \
  --http-method=POST
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | Required |
| `ADZUNA_APP_ID` | Adzuna API ID | Required |
| `ADZUNA_APP_KEY` | Adzuna API key | Required |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `TOP_K` | Max adaptive keywords | 8 |
| `DAILY_COUNT` | Jobs per daily digest | 5 |
| `DECAY` | Weight decay factor | 0.98 |
| `LIKE_BOOST` | Weight increase on like | 1.0 |
| `DISLIKE_PENALTY` | Weight decrease on dislike | -1.0 |

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
