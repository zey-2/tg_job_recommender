"""
Setup validation script - checks if environment is properly configured.
Run this before starting the bot to verify everything is ready.
"""
import sys
import os


def check_dependencies():
    """Check if all required packages are installed."""
    print("Checking dependencies...")
    required = [
        ('telegram', 'python-telegram-bot'),
        ('openai', 'openai'),
        ('requests', 'requests'),
        ('dotenv', 'python-dotenv'),
        ('pytz', 'pytz')
    ]
    
    missing = []
    for module, package in required:
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False
    
    print("✓ All dependencies installed\n")
    return True


def check_env_file():
    """Check if .env file exists and has required variables."""
    print("Checking environment configuration...")
    
    if not os.path.exists('.env'):
        print("  ✗ .env file not found")
        print("  Copy .env.example to .env and fill in your credentials")
        return False
    
    print("  ✓ .env file exists")
    
    # Load env vars
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'ADZUNA_APP_ID',
        'ADZUNA_APP_KEY',
        'OPENAI_API_KEY'
    ]
    
    missing = []
    placeholder_values = ['your_', 'sk-proj-']
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            print(f"  ✗ {var} - NOT SET")
            missing.append(var)
        elif any(ph in value for ph in placeholder_values):
            print(f"  ⚠ {var} - Still has placeholder value")
            missing.append(var)
        else:
            # Mask the value for security
            masked = value[:8] + '...' if len(value) > 8 else '***'
            print(f"  ✓ {var} = {masked}")
    
    if missing:
        print(f"\n❌ Please set these variables in .env: {', '.join(missing)}")
        return False
    
    print("✓ All required environment variables set\n")
    return True


def check_database():
    """Check if database can be initialized."""
    print("Checking database...")
    
    try:
        from database import get_db
        db = get_db()
        print("  ✓ Database initialized")
        print(f"  ✓ Database path: {db.db_path}")
        
        # Try a simple query
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  ✓ Tables created: {', '.join(tables)}")
        
        print("✓ Database ready\n")
        return True
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        return False


def check_apis():
    """Quick API connectivity check."""
    print("Checking API connectivity...")
    
    # Check Telegram
    try:
        from telegram import Bot
        import config
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        # This will raise an error if token is invalid
        print("  ✓ Telegram bot token valid")
    except Exception as e:
        print(f"  ✗ Telegram error: {e}")
        print("    Check your TELEGRAM_BOT_TOKEN")
        return False
    
    # Check Adzuna (simple request)
    try:
        import requests
        import config
        url = "https://api.adzuna.com/v1/api/jobs/sg/search/1"
        params = {
            "app_id": config.ADZUNA_APP_ID,
            "app_key": config.ADZUNA_APP_KEY,
            "results_per_page": 1,
            "what": "developer"
        }
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            print("  ✓ Adzuna API credentials valid")
        else:
            print(f"  ✗ Adzuna API error: {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ Adzuna error: {e}")
        print("    Check your ADZUNA credentials")
        return False
    
    # Check OpenAI
    try:
        from openai import OpenAI
        import config
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        # Simple test call
        client.models.list()
        print("  ✓ OpenAI API key valid")
    except Exception as e:
        print(f"  ✗ OpenAI error: {e}")
        print("    Check your OPENAI_API_KEY")
        return False
    
    print("✓ All APIs accessible\n")
    return True


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("TELEGRAM JOB BOT - SETUP VALIDATION")
    print("=" * 60)
    print()
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Environment", check_env_file),
        ("Database", check_database),
        ("APIs", check_apis)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} check failed with error: {e}\n")
            results.append((name, False))
    
    # Summary
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All checks passed! You're ready to run the bot.")
        print("\nStart the bot with: python main.py")
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        print("\nSee QUICKSTART.md for setup instructions.")
        sys.exit(1)


if __name__ == "__main__":
    main()
