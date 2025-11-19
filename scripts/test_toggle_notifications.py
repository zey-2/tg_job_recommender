"""Manual test script to verify toggle notification behavior and printed time."""
import asyncio
import os
import sys
from types import SimpleNamespace

# Ensure repository root is on sys.path so we can import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot import JobBot
from database import get_db


class FakeMessage:
    def __init__(self):
        self.last_text = None

    async def reply_text(self, text, parse_mode=None):
        self.last_text = text
        print(text)


class FakeUpdate:
    def __init__(self, user_id):
        self.effective_user = SimpleNamespace(id=user_id)
        self.message = FakeMessage()


async def main():
    db = get_db()
    user_id = 999999
    # Ensure user exists
    db.create_user(user_id, username='testuser')
    # Set a custom notification time
    db.set_notification_time(user_id, '10:30')

    bot = JobBot()
    update = FakeUpdate(user_id)

    print('\n--- Toggling ON ---')
    await bot.toggle_notifications_command(update, None)

    print('\n--- Toggling OFF ---')
    await bot.toggle_notifications_command(update, None)

    print('\n--- Toggling ON (again) ---')
    await bot.toggle_notifications_command(update, None)

if __name__ == '__main__':
    asyncio.run(main())
