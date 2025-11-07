# Conda Environment Setup Guide

## Environment Created ✅

Your conda environment `telegram-job-bot` has been created/updated with all dependencies.

## Activate Environment

```powershell
conda activate telegram-job-bot
```

## Installed Packages

### Core Dependencies
- `python=3.11`
- `python-telegram-bot==20.8` - Telegram bot API
- `requests==2.31.0` - HTTP client
- `python-dotenv==1.0.0` - Environment variables
- `SQLAlchemy==2.0.23` - Database ORM
- `pydantic==2.5.3` - Data validation
- `openai==1.54.3` - LLM integration
- `pytz==2024.1` - Timezone handling
- `tzdata==2024.1` - Timezone data

### Development Dependencies
- `pytest==7.4.3` - Testing framework
- `pytest-asyncio==0.21.1` - Async testing

## Quick Start

1. **Activate environment:**
   ```powershell
   conda activate telegram-job-bot
   ```

2. **Verify installation:**
   ```powershell
   python validate_setup.py
   ```

3. **Run the bot:**
   ```powershell
   python main.py
   ```

## Environment Management

### Update environment with new dependencies:
```powershell
conda env update -f environment.yml --prune
```

### Export current environment:
```powershell
conda env export > environment-lock.yml
```

### Remove environment:
```powershell
conda deactivate
conda env remove -n telegram-job-bot
```

### Recreate environment:
```powershell
conda env create -f environment.yml
```

## Troubleshooting

### If packages are missing:
```powershell
conda activate telegram-job-bot
pip install -r requirements.txt
```

### If environment conflicts:
```powershell
conda env remove -n telegram-job-bot
conda env create -f environment.yml
```

### Check installed packages:
```powershell
conda activate telegram-job-bot
conda list
```

## Next Steps

✅ Environment is ready!
✅ All dependencies installed!

Now you can:
1. Edit `.env` with your API credentials
2. Run `python validate_setup.py` to check configuration
3. Run `python main.py` to start the bot
