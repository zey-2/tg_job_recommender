# Database Clearing Script

This script (`clear_database.py`) allows you to clear various parts of the Telegram Job Bot database.

## Usage

```bash
python clear_database.py [option]
```

## Options

- `all` - Clear ALL data (complete database reset)
- `users` - Clear user data only (users, keywords, interactions)
- `jobs` - Clear job cache only
- `interactions` - Clear interaction history only
- `--help` - Show help message

## Examples

```bash
# Show current database status
python clear_database.py

# Clear all data (complete reset)
python clear_database.py all

# Clear only user data
python clear_database.py users

# Clear only job cache
python clear_database.py jobs

# Clear only interaction history
python clear_database.py interactions
```

## Safety Features

- **Confirmation required**: All destructive operations require typing "yes" to confirm
- **Status display**: Shows current database contents before and after operations
- **Foreign key handling**: Properly handles SQLite foreign key constraints
- **Auto-increment reset**: Resets SQLite auto-increment counters after clearing

## What Gets Cleared

### `all`
- All users and their data
- All keywords
- All cached jobs
- All interaction history

### `users`
- All user accounts
- All user keywords
- All interaction history
- **Jobs cache remains intact**

### `jobs`
- All cached job data
- **Users, keywords, and interactions remain intact**

### `interactions`
- All user interaction history
- **Users, keywords, and jobs remain intact**

## Database Tables

The script manages these tables:
- `users` - User accounts and preferences
- `user_keywords` - User keyword profiles
- `jobs` - Cached job data from Adzuna API
- `interactions` - User interactions with jobs (likes, dislikes, shown)