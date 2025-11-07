#!/usr/bin/env python3
"""
Database clearing script for Telegram Job Bot.

This script provides options to clear various parts of the database:
- All data (complete reset)
- User data only (users, keywords, interactions)
- Job cache only (jobs table)
- Interaction history only (interactions table)

Usage:
    python clear_database.py [option]

Options:
    all         - Clear all data (complete reset)
    users       - Clear user data (users, keywords, interactions)
    jobs        - Clear job cache only
    interactions - Clear interaction history only
    --help      - Show this help message
"""

import sqlite3
import sys
import os
from pathlib import Path
import config


class DatabaseClearer:
    """Handles database clearing operations."""

    def __init__(self, db_path: str = None):
        """Initialize with database path."""
        self.db_path = db_path or config.DATABASE_PATH
        if not os.path.exists(self.db_path):
            print(f"❌ Database file not found: {self.db_path}")
            sys.exit(1)

    def connect(self):
        """Connect to database."""
        return sqlite3.connect(self.db_path)

    def get_table_counts(self, conn):
        """Get row counts for all tables."""
        cursor = conn.cursor()
        tables = ['users', 'user_keywords', 'jobs', 'interactions']
        counts = {}

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                counts[table] = 0

        return counts

    def clear_all_data(self, conn):
        """Clear all data from all tables."""
        cursor = conn.cursor()

        print("🗑️  Clearing all data...")

        # Disable foreign key constraints temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")

        # Clear tables in correct order (respecting foreign keys)
        tables = ['interactions', 'user_keywords', 'users', 'jobs']
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            print(f"   Cleared {table} table")

        # Reset auto-increment counters
        cursor.execute("DELETE FROM sqlite_sequence")

        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")

        conn.commit()
        print("✅ All data cleared successfully")

    def clear_user_data(self, conn):
        """Clear user-related data (users, keywords, interactions)."""
        cursor = conn.cursor()

        print("👥 Clearing user data...")

        # Clear in order to respect foreign keys
        cursor.execute("DELETE FROM interactions")
        print("   Cleared interactions table")

        cursor.execute("DELETE FROM user_keywords")
        print("   Cleared user_keywords table")

        cursor.execute("DELETE FROM users")
        print("   Cleared users table")

        # Reset auto-increment counters
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('users', 'user_keywords', 'interactions')")

        conn.commit()
        print("✅ User data cleared successfully")

    def clear_job_cache(self, conn):
        """Clear job cache only."""
        cursor = conn.cursor()

        print("💼 Clearing job cache...")

        cursor.execute("DELETE FROM jobs")
        print("   Cleared jobs table")

        conn.commit()
        print("✅ Job cache cleared successfully")

    def clear_interactions(self, conn):
        """Clear interaction history only."""
        cursor = conn.cursor()

        print("📊 Clearing interaction history...")

        cursor.execute("DELETE FROM interactions")
        print("   Cleared interactions table")

        # Reset auto-increment counter
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'interactions'")

        conn.commit()
        print("✅ Interaction history cleared successfully")

    def show_status(self):
        """Show current database status."""
        conn = self.connect()
        counts = self.get_table_counts(conn)
        conn.close()

        print("📊 Current Database Status:")
        print(f"   Users: {counts['users']}")
        print(f"   Keywords: {counts['user_keywords']}")
        print(f"   Jobs: {counts['jobs']}")
        print(f"   Interactions: {counts['interactions']}")
        print(f"   Database: {self.db_path}")

    def confirm_action(self, action_description: str) -> bool:
        """Get user confirmation for destructive action."""
        print(f"\n⚠️  WARNING: This will {action_description}")
        print("This action cannot be undone!")

        while True:
            response = input("Are you sure? (type 'yes' to confirm): ").strip().lower()
            if response == 'yes':
                return True
            elif response in ['no', 'n', '']:
                return False
            else:
                print("Please type 'yes' to confirm or 'no' to cancel.")


def main():
    """Main function."""
    if len(sys.argv) < 2 or sys.argv[1] in ['--help', '-h', 'help']:
        print(__doc__)
        return

    action = sys.argv[1].lower()

    # Initialize clearer
    clearer = DatabaseClearer()

    # Show current status
    clearer.show_status()

    # Process action
    conn = clearer.connect()

    try:
        if action == 'all':
            if clearer.confirm_action("permanently delete ALL data from the database"):
                clearer.clear_all_data(conn)
            else:
                print("❌ Operation cancelled")

        elif action == 'users':
            if clearer.confirm_action("permanently delete all user data (users, keywords, and interactions)"):
                clearer.clear_user_data(conn)
            else:
                print("❌ Operation cancelled")

        elif action == 'jobs':
            if clearer.confirm_action("permanently delete all cached job data"):
                clearer.clear_job_cache(conn)
            else:
                print("❌ Operation cancelled")

        elif action == 'interactions':
            if clearer.confirm_action("permanently delete all interaction history"):
                clearer.clear_interactions(conn)
            else:
                print("❌ Operation cancelled")

        else:
            print(f"❌ Unknown action: {action}")
            print("Use --help for available options")
            return

        # Show final status
        print("\n" + "="*50)
        clearer.show_status()

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()