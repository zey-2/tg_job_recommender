"""Database models and operations for the Telegram Job Bot."""
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pytz import timezone
import config


class Database:
    """SQLite database manager for job bot."""
    
    def __init__(self, db_path: str = None):
        """Initialize database connection."""
        self.db_path = db_path or config.DATABASE_PATH
        self.conn = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to SQLite database."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
    
    def create_tables(self):
        """Create all necessary tables."""
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                tg_username TEXT,
                prefs_json TEXT DEFAULT '{}',
                notifications_enabled INTEGER DEFAULT 1,
                notification_time TEXT DEFAULT '09:00',
                min_salary_preference INTEGER DEFAULT NULL,
                timezone TEXT DEFAULT 'Asia/Singapore',
                next_digest_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User keywords table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                is_negative INTEGER DEFAULT 0,
                source TEXT DEFAULT 'auto',
                rationale TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, keyword)
            )
        """)
        
        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                description TEXT,
                url TEXT,
                salary_min REAL,
                salary_max REAL,
                salary_currency TEXT,
                salary_interval TEXT,
                salary_display_text TEXT,
                salary_hidden INTEGER DEFAULT 0,
                category_json TEXT,
                employment_type_json TEXT,
                work_arrangement TEXT,
                mrt_stations_json TEXT,
                skills_json TEXT,
                position_level TEXT,
                experience_required TEXT,
                education_required TEXT,
                timing_shift_json TEXT,
                activation_date TEXT,
                expiration_date TEXT,
                source TEXT DEFAULT 'findsgjobs',
                posted_at TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Interactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id TEXT NOT NULL,
                action TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_keywords_user ON user_keywords(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user ON interactions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_job ON interactions(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_digest_time ON users(next_digest_at)")
        # Daily cache table for small globally-shared values (e.g., today's encouragement message)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_cache (
                cache_key TEXT PRIMARY KEY,
                cache_value TEXT NOT NULL,
                cache_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_cache_date ON daily_cache(cache_date)")
        
        self.conn.commit()
        # Ensure 'source' column exists for compatibility with older DBs
        cursor.execute("PRAGMA table_info(user_keywords)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'source' not in cols:
            try:
                cursor.execute("ALTER TABLE user_keywords ADD COLUMN source TEXT DEFAULT 'auto'")
                self.conn.commit()
            except Exception:
                # If alter table fails, log silently and continue
                pass

        # API rate limiting table for timestamp-based windows
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_rate_limit (
                api_name TEXT PRIMARY KEY,
                window_start REAL,
                request_count INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    # Daily cache helpers
    def get_daily_cache(self, cache_key: str, expected_date: str):
        """Return cached value for key if it exists for expected_date, else None."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT cache_value FROM daily_cache WHERE cache_key = ? AND cache_date = ?", (cache_key, expected_date))
        row = cursor.fetchone()
        return row[0] if row else None

    def set_daily_cache(self, cache_key: str, cache_value: str, cache_date: str):
        """Set or update a cached value for a given date.

        Uses an upsert so updates replace previous entries.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO daily_cache (cache_key, cache_value, cache_date)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                cache_value = excluded.cache_value,
                cache_date = excluded.cache_date,
                created_at = CURRENT_TIMESTAMP
        """, (cache_key, cache_value, cache_date))
        self.conn.commit()

    def cleanup_old_cache(self, days_to_keep: int = 7):
        """Remove cache entries older than days_to_keep to prevent table growth."""
        cursor = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days_to_keep)).date().isoformat()
        cursor.execute("DELETE FROM daily_cache WHERE cache_date < ?", (cutoff,))
        self.conn.commit()
    
    # User operations
    def create_user(self, user_id: int, username: str = None, prefs: dict = None) -> bool:
        """Create a new user."""
        cursor = self.conn.cursor()
        try:
            prefs_json = json.dumps(prefs or {})
            # Calculate next digest time (default 9:00 AM next day)
            next_digest = self._calculate_next_digest(config.DEFAULT_NOTIFICATION_TIME)
            
            cursor.execute("""
                INSERT INTO users (user_id, tg_username, prefs_json, 
                                 notifications_enabled, notification_time, next_digest_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, prefs_json, 
                  1 if config.DEFAULT_NOTIFICATIONS else 0,
                  config.DEFAULT_NOTIFICATION_TIME,
                  next_digest))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def update_user_prefs(self, user_id: int, prefs: dict):
        """Update user preferences."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET prefs_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (json.dumps(prefs), user_id))
        self.conn.commit()

    def update_user_min_salary(self, user_id: int, min_salary: int):
        """Set user's monthly min salary preference (SGD). Use NULL to clear."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users SET min_salary_preference = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (min_salary, user_id))
        self.conn.commit()

    def get_user_min_salary(self, user_id: int) -> Optional[int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT min_salary_preference FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def wait_for_rate_limit(self, api_name: str, max_requests: int, window_seconds: int = 60) -> int:
        """Ensure a maximum of `max_requests` in `window_seconds` window for the given api_name.
        Returns seconds waited (0 if no wait).
        """
        cursor = self.conn.cursor()
        now = datetime.now().timestamp()
        cursor.execute("SELECT window_start, request_count FROM api_rate_limit WHERE api_name = ?", (api_name,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO api_rate_limit (api_name, window_start, request_count) VALUES (?, ?, 1)", (api_name, now))
            self.conn.commit()
            return 0

        window_start, count = row
        # window_start can be None if reset earlier
        if window_start is None:
            window_start = now

        elapsed = now - window_start
        if elapsed >= window_seconds:
            # Reset window and count this request
            cursor.execute("UPDATE api_rate_limit SET window_start = ?, request_count = 1 WHERE api_name = ?", (now, api_name))
            self.conn.commit()
            return 0

        if count < max_requests:
            # Increment count for this request
            cursor.execute("UPDATE api_rate_limit SET request_count = request_count + 1 WHERE api_name = ?", (api_name,))
            self.conn.commit()
            return 0

        # Need to wait until window resets - return wait time, do NOT sleep here
        wait_seconds = int(window_seconds - elapsed) + 1
        return wait_seconds
    
    def toggle_notifications(self, user_id: int) -> bool:
        """Toggle user notifications. Returns new state."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT notifications_enabled FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            new_state = 0 if row[0] else 1
            cursor.execute("""
                UPDATE users 
                SET notifications_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (new_state, user_id))
            self.conn.commit()
            return bool(new_state)
        return False
    
    def set_notification_time(self, user_id: int, time_str: str):
        """Set user notification time and recalculate next digest."""
        next_digest = self._calculate_next_digest(time_str)
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET notification_time = ?, next_digest_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (time_str, next_digest, user_id))
        self.conn.commit()
    
    def _calculate_next_digest(self, time_str: str) -> str:
        """Calculate next digest datetime based on notification time."""
        now = datetime.now(timezone(config.DEFAULT_TIMEZONE))
        hour, minute = map(int, time_str.split(':'))
        
        # Set to today at notification time (localized)
        next_digest = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If time has passed, move to tomorrow
        if next_digest <= now:
            next_digest += timedelta(days=1)
        
        return next_digest.isoformat()
    
    def get_users_for_digest(self) -> List[Dict]:
        """Get users who are due for daily digest."""
        cursor = self.conn.cursor()
        now = datetime.now(timezone(config.DEFAULT_TIMEZONE)).isoformat()
        cursor.execute("""
            SELECT * FROM users 
            WHERE notifications_enabled = 1 
            AND next_digest_at <= ?
        """, (now,))
        return [dict(row) for row in cursor.fetchall()]
    
    def update_next_digest(self, user_id: int):
        """Advance user's next digest by 24 hours."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT next_digest_at, notification_time FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row[0]:
            current_digest = datetime.fromisoformat(row[0])
            next_digest = current_digest + timedelta(days=1)
            cursor.execute("""
                UPDATE users 
                SET next_digest_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (next_digest.isoformat(), user_id))
            self.conn.commit()

    def reserve_due_users_for_digest(self, now_iso: str) -> List[Dict]:
        """Atomically reserve users who are due for digest and advance their next_digest_at by 1 day.

        This method uses an immediate transaction to prevent race conditions when multiple
        scheduler instances attempt to reserve the same users. Returns the list of user records reserved.
        """
        cursor = self.conn.cursor()
        users = []
        try:
            # Start immediate transaction to acquire write lock
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "SELECT user_id, next_digest_at FROM users WHERE notifications_enabled = 1 AND next_digest_at <= ?",
                (now_iso,)
            )
            rows = cursor.fetchall()
            if not rows:
                cursor.execute("COMMIT")
                return []

            # Advance each user's next_digest_at by 1 day (calculate with Python to preserve ISO tz info)
            user_ids = []
            for r in rows:
                uid = r[0]
                nd = r[1]
                if not nd:
                    continue
                current_digest = datetime.fromisoformat(nd)
                next_digest = (current_digest + timedelta(days=1)).isoformat()
                cursor.execute(
                    "UPDATE users SET next_digest_at = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                    (next_digest, uid)
                )
                user_ids.append(uid)

            # Commit transaction
            cursor.execute("COMMIT")

            # Return full user records
            users = []
            for uid in user_ids:
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
                row = cursor.fetchone()
                if row:
                    users.append(dict(row))
            return users

        except Exception:
            cursor.execute("ROLLBACK")
            raise
    
    # Keyword operations
    def get_user_keywords(self, user_id: int, top_k: int = None) -> List[Dict]:
        """Get user keywords sorted by weight."""
        cursor = self.conn.cursor()
        query = """
            SELECT * FROM user_keywords 
            WHERE user_id = ? 
            ORDER BY weight DESC
        """
        if top_k:
            query += f" LIMIT {top_k}"
        
        cursor.execute(query, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def upsert_keyword(self, user_id: int, keyword: str, weight: float, 
                      is_negative: bool = False, rationale: str = None, source: str = 'auto'):
        """Insert or update a keyword."""
        cursor = self.conn.cursor()
        # If inserting or updating, avoid auto-generated updates overwriting manual keywords.
        # If existing source is 'manual' and new source is 'auto', keep existing values.
        # Enforce manual keywords are always positive
        if source == 'manual':
            is_negative = False

        cursor.execute("""
            INSERT INTO user_keywords (user_id, keyword, weight, is_negative, rationale, source)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, keyword)
            DO UPDATE SET
                weight = CASE WHEN source = 'manual' AND excluded.source = 'auto' THEN weight ELSE excluded.weight END,
                is_negative = CASE WHEN source = 'manual' AND excluded.source = 'auto' THEN is_negative ELSE excluded.is_negative END,
                rationale = CASE WHEN source = 'manual' AND excluded.source = 'auto' THEN rationale ELSE excluded.rationale END,
                source = CASE WHEN source = 'manual' AND excluded.source = 'auto' THEN source ELSE excluded.source END,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, keyword.lower(), weight, 1 if is_negative else 0, rationale, source))
        self.conn.commit()
    
    def update_keyword_weight(self, user_id: int, keyword: str, delta: float):
        """Update keyword weight by delta."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE user_keywords 
            SET weight = weight + ?, 
                is_negative = CASE WHEN (weight + ?) < ? THEN 1 ELSE 0 END,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND keyword = ?
        """, (delta, delta, config.NEGATIVE_PROMOTE_AT, user_id, keyword.lower()))
        self.conn.commit()
    
    def delete_keywords(self, user_id: int, keywords: List[str]):
        """Delete specific keywords."""
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(keywords))
        cursor.execute(f"""
            DELETE FROM user_keywords 
            WHERE user_id = ? AND keyword IN ({placeholders})
        """, [user_id] + [k.lower() for k in keywords])
        self.conn.commit()

    def delete_keyword(self, user_id: int, keyword: str):
        """Delete a single keyword for user."""
        self.delete_keywords(user_id, [keyword])

    def get_keyword_by_id(self, user_id: int, keyword_id: int) -> Optional[Dict]:
        """Get a keyword row by its id for a given user."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM user_keywords WHERE id = ? AND user_id = ?", (keyword_id, user_id))
        row = cursor.fetchone()
        return dict(row) if row else None

    def delete_keyword_by_id(self, user_id: int, keyword_id: int):
        """Delete a keyword by its id for a given user."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM user_keywords WHERE id = ? AND user_id = ?", (keyword_id, user_id))
        self.conn.commit()

    def clear_auto_keywords(self, user_id: int):
        """Delete all auto-generated keywords for the user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM user_keywords
            WHERE user_id = ? AND (source IS NULL OR source != 'manual')
        """, (user_id,))
        self.conn.commit()

    def clear_manual_keywords(self, user_id: int):
        """Delete all manual keywords for the user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM user_keywords
            WHERE user_id = ? AND source = 'manual'
        """, (user_id,))
        self.conn.commit()
    
    def decay_keywords(self, user_id: int, decay_factor: float):
        """Apply decay to all keywords."""
        cursor = self.conn.cursor()
        # Do not decay manual keywords (they have fixed weight)
        cursor.execute("""
            UPDATE user_keywords 
            SET weight = weight * ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND (source IS NULL OR source != 'manual')
        """, (decay_factor, user_id))
        self.conn.commit()

    def count_manual_keywords(self, user_id: int, positive_only: bool = True) -> int:
        """Return the count of manual keywords for a user. Optionally only positive ones."""
        cursor = self.conn.cursor()
        if positive_only:
            cursor.execute("SELECT COUNT(*) FROM user_keywords WHERE user_id = ? AND source = 'manual' AND is_negative = 0", (user_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM user_keywords WHERE user_id = ? AND source = 'manual'", (user_id,))
        return cursor.fetchone()[0]

    def count_auto_keywords(self, user_id: int, positive_only: bool = True) -> int:
        """Return the count of auto-generated keywords for a user. Optionally only positive ones."""
        cursor = self.conn.cursor()
        if positive_only:
            cursor.execute("SELECT COUNT(*) FROM user_keywords WHERE user_id = ? AND (source IS NULL OR source != 'manual') AND is_negative = 0", (user_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM user_keywords WHERE user_id = ? AND (source IS NULL OR source != 'manual')", (user_id,))
        return cursor.fetchone()[0]
    
    # Job operations
    def upsert_job(self, job_data: Dict):
        """Insert or update a job."""
        cursor = self.conn.cursor()
        # Ensure we have a safe title to avoid NOT NULL constraint failure
        title_safe = job_data.get('title') or (job_data.get('job', {}) or {}).get('Title') or (job_data.get('job', {}) or {}).get('title') or 'Unknown'
        try:
            cursor.execute("""
            INSERT INTO jobs (job_id, title, company, location, description, 
                            url, salary_min, salary_max, salary_currency, salary_interval, salary_display_text, salary_hidden,
                            category_json, employment_type_json, work_arrangement, mrt_stations_json, skills_json,
                            position_level, experience_required, education_required, timing_shift_json, activation_date, expiration_date, source, posted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) 
            DO UPDATE SET 
                title = excluded.title,
                company = excluded.company,
                location = excluded.location,
                description = excluded.description,
                url = excluded.url,
                salary_min = excluded.salary_min,
                salary_max = excluded.salary_max,
                salary_currency = excluded.salary_currency,
                salary_interval = excluded.salary_interval,
                salary_display_text = excluded.salary_display_text,
                salary_hidden = excluded.salary_hidden,
                category_json = excluded.category_json,
                employment_type_json = excluded.employment_type_json,
                work_arrangement = excluded.work_arrangement,
                mrt_stations_json = excluded.mrt_stations_json,
                skills_json = excluded.skills_json,
                position_level = excluded.position_level,
                experience_required = excluded.experience_required,
                education_required = excluded.education_required,
                timing_shift_json = excluded.timing_shift_json,
                activation_date = excluded.activation_date,
                expiration_date = excluded.expiration_date,
                source = excluded.source,
                posted_at = excluded.posted_at,
                fetched_at = CURRENT_TIMESTAMP
        """, (
            job_data.get('id') or job_data.get('job_id') or job_data.get('job', {}).get('id') or job_data.get('job', {}).get('sid'),
            title_safe,
            (job_data.get('company', {}).get('display_name') if isinstance(job_data.get('company'), dict) else job_data.get('company')) or (job_data.get('company') if isinstance(job_data.get('company'), str) else None),
            (job_data.get('location', {}).get('display_name') if isinstance(job_data.get('location'), dict) else job_data.get('location')) or (job_data.get('location') if isinstance(job_data.get('location'), str) else None),
            job_data.get('description'),
            job_data.get('url') or job_data.get('redirect_url'),
            job_data.get('salary_min'),
            job_data.get('salary_max'),
            job_data.get('salary_currency'),
            job_data.get('salary_interval'),
            job_data.get('salary_display_text'),
            job_data.get('salary_hidden', 0),
            job_data.get('category_json'),
            job_data.get('employment_type_json'),
            job_data.get('work_arrangement'),
            job_data.get('mrt_stations_json'),
            job_data.get('skills_json'),
            job_data.get('position_level'),
            job_data.get('experience_required'),
            job_data.get('education_required'),
            job_data.get('timing_shift_json'),
            job_data.get('activation_date'),
            job_data.get('expiration_date'),
            job_data.get('source'),
            job_data.get('created')
        ))
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            # Log and re-raise or ignore depending on policy; for now, log and skip
            logger = logging.getLogger(__name__)
            logger.warning("Failed to upsert job (IntegrityError): %s - job_id=%s, title=%s", e, job_data.get('id'), title_safe)
        except Exception:
            # Re-raise unexpected exceptions to surface them during development
            raise
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    # Interaction operations
    def log_interaction(self, user_id: int, job_id: str, action: str):
        """Log user interaction with a job."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO interactions (user_id, job_id, action)
            VALUES (?, ?, ?)
        """, (user_id, job_id, action))
        self.conn.commit()
    
    def get_user_interactions(self, user_id: int, action: str = None, 
                            days: int = 7) -> List[Dict]:
        """Get user interactions, optionally filtered by action and date."""
        cursor = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        query = "SELECT * FROM interactions WHERE user_id = ? AND timestamp >= ?"
        params = [user_id, cutoff]
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_recently_shown_jobs(self, user_id: int, days: int = 7) -> List[str]:
        """Get job IDs shown to user recently."""
        cursor = self.conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("""
            SELECT DISTINCT job_id FROM interactions 
            WHERE user_id = ? AND timestamp >= ?
        """, (user_id, cutoff))
        return [row[0] for row in cursor.fetchall()]

    def clear_user_interactions(self, user_id: int):
        """Delete all interactions for a user."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM interactions WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def reset_user_profile(self, user_id: int, keep_settings: bool = True):
        """Reset user profile by clearing keywords and interaction history.

        Args:
            user_id: The telegram user id
            keep_settings: If True, preserve notification enabled flag and prefs_json,
                          but still reset notification_time and min_salary_preference to defaults
        """
        cursor = self.conn.cursor()
        # Delete user keywords
        cursor.execute("DELETE FROM user_keywords WHERE user_id = ?", (user_id,))
        # Delete user interactions
        cursor.execute("DELETE FROM interactions WHERE user_id = ?", (user_id,))
        if keep_settings:
            # Reset notification_time and min_salary_preference to defaults, keep notifications_enabled and prefs_json
            cursor.execute("UPDATE users SET notification_time = ?, min_salary_preference = NULL, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (config.DEFAULT_NOTIFICATION_TIME, user_id))
        else:
            # Reset prefs_json to empty and clear notification settings
            cursor.execute("UPDATE users SET prefs_json = ?, notifications_enabled = ?, notification_time = ?, min_salary_preference = NULL, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (json.dumps({}), 1 if config.DEFAULT_NOTIFICATIONS else 0, config.DEFAULT_NOTIFICATION_TIME, user_id))
        self.conn.commit()

    def clear_all_negative_keywords(self):
        """Remove negative keywords for all users (migration aide)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM user_keywords WHERE is_negative = 1")
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


# Global database instance
_db = None

def get_db() -> Database:
    """Get global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
