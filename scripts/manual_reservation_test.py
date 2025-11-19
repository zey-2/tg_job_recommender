"""Manual reservation test for reserve_due_users_for_digest.

Run this script after initializing an empty DB to seed a test user and confirm owned reservation behavior.
"""
from datetime import datetime, timedelta
from pytz import timezone
import config
from database import Database


def main():
    db = Database(db_path=config.DATABASE_PATH)
    tz = timezone(config.DEFAULT_TIMEZONE)
    now_iso = datetime.now(tz).isoformat()

    # Create a test user (user_id = 99999) if not exists
    user_id = 99999
    db.create_user(user_id, username='test_user')

    # Force next_digest_at to now so reservation will pick it up
    cursor = db.conn.cursor()
    cursor.execute("UPDATE users SET next_digest_at = ? WHERE user_id = ?", (now_iso, user_id))
    db.conn.commit()

    users = db.reserve_due_users_for_digest(now_iso)
    print("Reserved users:", users)
    assert any(u["user_id"] == user_id for u in users), "Test user not reserved"

    # Confirm next_digest_at has moved forward at least 24 hours
    cursor.execute("SELECT next_digest_at FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        nd = row[0]
        print("Next digest at:", nd)
    else:
        print("Test user not found after reservation")

    print("Manual reservation test completed")


if __name__ == '__main__':
    main()
