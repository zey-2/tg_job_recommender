from database import get_db
from datetime import datetime
from pytz import timezone

db = get_db()

today = datetime.now(timezone('Asia/Singapore')).date().isoformat()
print('Today:', today)

try:
    db.set_daily_cache('encouragement_message', 'Unit test encouragement', today)
    val = db.get_daily_cache('encouragement_message', today)
    print('Cache value read:', val)
except Exception as e:
    print('Error:', e)
