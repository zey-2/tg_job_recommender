"""Smoke tests: DB daily cache and LLM generate_encouragement fallback.

This script uses local SQLite DB and does not require external services if OPENAI_API_KEY is not set.
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import get_db
from llm_service import get_llm_service
import config

# Ensure environment is set for tests
print('CONFIG ENCOURAGEMENT_ENABLED:', config.ENCOURAGEMENT_ENABLED)
print('DB PATH:', config.DATABASE_PATH)

def test_db_cache():
    db = get_db()
    key = 'encouragement_message'
    date = '2099-01-01'
    print('Set cache for key', key, 'date', date)
    db.set_daily_cache(key, 'Test Message', date)
    val = db.get_daily_cache(key, date)
    assert val == 'Test Message', f"Expected 'Test Message' got {val}"
    print('DB cache set/get OK')


def test_llm_fallback():
    # Clear any OPENAI_API_KEY to force fallback
    os.environ.pop('OPENAI_API_KEY', None)
    llm = get_llm_service()
    msg = llm.generate_encouragement()
    print('LLM returned message:', msg)
    assert msg and isinstance(msg, str), 'LLM generate_encouragement failed to return a string'
    print('LLM fallback OK')


if __name__ == '__main__':
    test_db_cache()
    test_llm_fallback()
    print('Smoke tests completed successfully')
