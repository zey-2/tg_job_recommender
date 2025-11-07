"""Database models and operations for the Telegram Job Bot."""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
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
        from pytz import timezone
        
        now = datetime.now(timezone(config.DEFAULT_TIMEZONE))
        hour, minute = map(int, time_str.split(':'))
        
        # Set to today at notification time
        next_digest = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If time has passed, move to tomorrow
        if next_digest <= now:
            next_digest += timedelta(days=1)
        
        return next_digest.isoformat()
    
    def get_users_for_digest(self) -> List[Dict]:
        """Get users who are due for daily digest."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
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
                      is_negative: bool = False, rationale: str = None):
        """Insert or update a keyword."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO user_keywords (user_id, keyword, weight, is_negative, rationale)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, keyword) 
            DO UPDATE SET 
                weight = excluded.weight,
                is_negative = excluded.is_negative,
                rationale = excluded.rationale,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, keyword.lower(), weight, 1 if is_negative else 0, rationale))
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
    
    def decay_keywords(self, user_id: int, decay_factor: float):
        """Apply decay to all keywords."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE user_keywords 
            SET weight = weight * ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (decay_factor, user_id))
        self.conn.commit()
    
    # Job operations
    def upsert_job(self, job_data: Dict):
        """Insert or update a job."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (job_id, title, company, location, description, 
                            url, salary_min, salary_max, posted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) 
            DO UPDATE SET 
                title = excluded.title,
                company = excluded.company,
                location = excluded.location,
                description = excluded.description,
                url = excluded.url,
                salary_min = excluded.salary_min,
                salary_max = excluded.salary_max,
                posted_at = excluded.posted_at,
                fetched_at = CURRENT_TIMESTAMP
        """, (
            job_data.get('id'),
            job_data.get('title'),
            job_data.get('company', {}).get('display_name') if isinstance(job_data.get('company'), dict) else job_data.get('company'),
            job_data.get('location', {}).get('display_name') if isinstance(job_data.get('location'), dict) else job_data.get('location'),
            job_data.get('description'),
            job_data.get('redirect_url'),
            job_data.get('salary_min'),
            job_data.get('salary_max'),
            job_data.get('created')
        ))
        self.conn.commit()
    
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
