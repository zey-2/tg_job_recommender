# Quick Start Guide

## Step 1: Install Dependencies

Open PowerShell and run:
```powershell
pip install -r requirements.txt
```

## Step 2: Set Up Environment Variables

1. Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

2. Edit `.env` and add your credentials:
   - Get Telegram bot token from @BotFather
   - Register at Adzuna Developer Portal for API credentials
   - Get OpenAI API key from platform.openai.com

## Step 3: Run the Bot

```powershell
python main.py
```

The bot will start in polling mode (for development).

## Testing Commands

Once the bot is running, open Telegram and:

1. Start a chat with your bot
2. Send `/start` to register
3. Send `/more` to get job recommendations
4. Like or dislike jobs to train your profile
5. Send `/keywords` to see your adaptive profile

## Troubleshooting

### Import Errors
If you see import errors, make sure you've installed all dependencies:
```powershell
pip install python-telegram-bot openai requests python-dotenv pytz
```

### Database Errors
The bot will automatically create `job_bot.db` on first run.

### API Errors
- Check that your `.env` file has valid credentials
- Ensure you have internet connection
- Verify API quotas haven't been exceeded

## Next Steps

- Use `/search python developer` to test job search
- Set notification time with `/set_time 09:00`
- View your profile with `/keywords`
