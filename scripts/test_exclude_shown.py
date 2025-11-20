"""Test script to verify that shown jobs are properly excluded from recommendations."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db
from datetime import datetime, timedelta

def test_exclude_shown_jobs():
    """Verify that get_recently_shown_jobs includes 'shown' interactions."""
    db = get_db()
    
    # Create a test user
    test_user_id = 999999  # Use a high ID to avoid conflicts
    db.create_user(test_user_id, username="test_user")
    
    # Clear any existing interactions for this test user
    db.clear_user_interactions(test_user_id)
    
    # Log some interactions
    test_jobs = [
        ('job_shown_1', 'shown'),
        ('job_shown_2', 'shown'),
        ('job_liked_1', 'like'),
        ('job_disliked_1', 'dislike'),
    ]
    
    for job_id, action in test_jobs:
        db.log_interaction(test_user_id, job_id, action)
    
    # Get recently shown jobs (should include all actions)
    recent = db.get_recently_shown_jobs(test_user_id, days=7)
    
    print(f"\n✅ Test Results:")
    print(f"Total interactions logged: {len(test_jobs)}")
    print(f"Recently shown jobs (excluded): {len(recent)}")
    print(f"Job IDs: {recent}")
    
    # Verify all jobs are included
    expected = {'job_shown_1', 'job_shown_2', 'job_liked_1', 'job_disliked_1'}
    actual = set(recent)
    
    if expected == actual:
        print(f"\n✅ SUCCESS: All shown/liked/disliked jobs are properly excluded!")
        print(f"Expected: {expected}")
        print(f"Actual: {actual}")
    else:
        print(f"\n❌ FAILURE: Mismatch in excluded jobs")
        print(f"Expected: {expected}")
        print(f"Actual: {actual}")
        print(f"Missing: {expected - actual}")
        print(f"Extra: {actual - expected}")
    
    # Cleanup
    db.clear_user_interactions(test_user_id)
    print(f"\n🧹 Cleaned up test data")

if __name__ == "__main__":
    test_exclude_shown_jobs()
