"""Keyword management and job scoring logic."""
import re
from typing import List, Dict, Tuple
from collections import Counter
import config
from database import get_db
from llm_service import get_llm_service


class KeywordManager:
    """Manages user keywords and scores jobs."""
    
    def __init__(self):
        """Initialize keyword manager."""
        self.db = get_db()
        self.llm = get_llm_service()
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words."""
        if not text:
            return []
        # Remove special characters and split
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        tokens = text.split()
        # Filter out very short tokens
        return [t for t in tokens if len(t) > 2]
    
    def score_job(self, job: Dict, user_keywords: List[Dict]) -> Tuple[float, List[str]]:
        """
        Score a job based on user keywords.
        
        Args:
            job: Job dictionary
            user_keywords: List of user keyword dicts with weight and is_negative
            
        Returns:
            Tuple of (score, matched_keywords)
        """
        # Tokenize job content
        title_tokens = self.tokenize(job.get('title', ''))
        desc_tokens = self.tokenize(job.get('description', ''))
        company_tokens = self.tokenize(
            job.get('company', {}).get('display_name', '') 
            if isinstance(job.get('company'), dict) 
            else str(job.get('company', ''))
        )
        
        # Combine all tokens
        all_tokens = title_tokens + desc_tokens + company_tokens
        token_counts = Counter(all_tokens)
        
        # Calculate score
        score = 0.0
        matched_keywords = []
        negative_match = False
        
        for kw_data in user_keywords:
            keyword = kw_data['keyword'].lower()
            weight = kw_data['weight']
            is_negative = bool(kw_data['is_negative'])
            
            # Check if keyword appears in tokens
            if keyword in token_counts:
                matched_keywords.append(keyword)
                
                # Hard negative filter - immediately reject
                if is_negative and weight < config.NEGATIVE_PROMOTE_AT:
                    return -1000.0, [keyword]
                
                # Soft negative - subtract weight
                if is_negative:
                    score -= abs(weight)
                    negative_match = True
                else:
                    # Positive match - add weight
                    # Cap contribution to avoid single keyword dominance
                    contribution = min(weight, 5.0)
                    score += contribution
        
        # Penalty if only negative matches
        if negative_match and score <= 0:
            score -= 5.0
        
        # Small boost for title matches (title is more important)
        title_match_bonus = sum(
            0.5 for kw_data in user_keywords 
            if kw_data['keyword'] in title_tokens and not kw_data['is_negative']
        )
        score += title_match_bonus
        
        return max(score, 0.0), matched_keywords
    
    def rank_jobs(self, jobs: List[Dict], user_id: int, 
                 exclude_recent: bool = True) -> List[Tuple[Dict, float, List[str]]]:
        """
        Rank jobs for a user.
        
        Args:
            jobs: List of job dictionaries
            user_id: User ID
            exclude_recent: Whether to exclude recently shown jobs
            
        Returns:
            List of (job, score, matched_keywords) tuples, sorted by score
        """
        # Get user keywords
        user_keywords = self.db.get_user_keywords(user_id)
        
        if not user_keywords:
            # No keywords yet - return jobs with neutral scoring
            return [(job, 1.0, []) for job in jobs]
        
        # Get recently shown jobs if needed
        recent_job_ids = set()
        if exclude_recent:
            recent_job_ids = set(self.db.get_recently_shown_jobs(user_id, days=7))
        
        # Score and filter jobs
        scored_jobs = []
        for job in jobs:
            job_id = job.get('id')
            
            # Skip recently shown jobs
            if job_id in recent_job_ids:
                continue
            
            score, matched = self.score_job(job, user_keywords)
            
            # Skip jobs with negative scores (hard negatives)
            if score < 0:
                continue
            
            scored_jobs.append((job, score, matched))
        
        # Sort by score descending
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        
        return scored_jobs
    
    def update_keywords_from_feedback(self, user_id: int, job: Dict, action: str):
        """
        Update user keywords based on job feedback.
        
        Args:
            user_id: User ID
            job: Job dictionary
            action: 'like' or 'dislike'
        """
        # Get current keywords
        current_keywords = self.db.get_user_keywords(user_id)
        
        # Extract job info
        job_title = job.get('title', '')
        company = job.get('company', {})
        if isinstance(company, dict):
            company = company.get('display_name', '')
        description = job.get('description', '')[:500]  # Truncate
        
        # Get LLM keyword suggestions
        llm_suggestions = self.llm.expand_keywords(
            job_title=job_title,
            company=str(company),
            description=description,
            current_keywords=current_keywords,
            user_reaction=action
        )
        
        # Determine weight delta based on action
        if action == 'like':
            base_delta = config.LIKE_BOOST
        elif action == 'dislike':
            base_delta = config.DISLIKE_PENALTY
        else:
            base_delta = 0.0
        
        # Process LLM suggestions
        for suggestion in llm_suggestions:
            keyword = suggestion['keyword']
            sentiment = suggestion['sentiment']
            rationale = suggestion.get('rationale', '')
            
            # Find if keyword exists
            existing = next((kw for kw in current_keywords if kw['keyword'] == keyword), None)
            
            if existing:
                # Update existing keyword
                # Adjust based on sentiment alignment
                if action == 'like' and sentiment == 'positive':
                    delta = base_delta
                elif action == 'dislike' and sentiment == 'negative':
                    delta = abs(base_delta)  # Reinforce negative
                elif action == 'like' and sentiment == 'negative':
                    delta = -abs(base_delta) * 0.5  # Conflicting signal
                elif action == 'dislike' and sentiment == 'positive':
                    delta = base_delta * 0.5  # Conflicting signal
                else:
                    delta = 0.0
                
                new_weight = existing['weight'] + delta
                is_negative = new_weight < config.NEGATIVE_PROMOTE_AT
                
                self.db.upsert_keyword(
                    user_id=user_id,
                    keyword=keyword,
                    weight=new_weight,
                    is_negative=is_negative,
                    rationale=rationale
                )
            else:
                # New keyword - seed with appropriate weight
                if action == 'like' and sentiment == 'positive':
                    initial_weight = 1.0
                    is_negative = False
                elif action == 'dislike' and sentiment == 'negative':
                    initial_weight = -1.0
                    is_negative = True
                else:
                    initial_weight = 0.5 if sentiment == 'positive' else -0.5
                    is_negative = sentiment == 'negative'
                
                self.db.upsert_keyword(
                    user_id=user_id,
                    keyword=keyword,
                    weight=initial_weight,
                    is_negative=is_negative,
                    rationale=rationale
                )
        
        # Apply decay to all keywords
        self.db.decay_keywords(user_id, config.DECAY)
        
        # Prune low-weight keywords (keep top K positive + all active negatives)
        self._prune_keywords(user_id)
    
    def _prune_keywords(self, user_id: int):
        """Keep only top K keywords plus active negatives."""
        all_keywords = self.db.get_user_keywords(user_id)
        
        # Separate positive and negative
        positive = [kw for kw in all_keywords if not kw['is_negative']]
        negative = [kw for kw in all_keywords if kw['is_negative']]
        
        # Keep top K positive
        positive.sort(key=lambda x: x['weight'], reverse=True)
        keep_positive = positive[:config.TOP_K]
        
        # Keep all negatives with weight below threshold
        keep_negative = [kw for kw in negative if kw['weight'] < config.NEGATIVE_PROMOTE_AT]
        
        # Identify keywords to delete
        keep_keywords = set(kw['keyword'] for kw in keep_positive + keep_negative)
        all_keyword_names = set(kw['keyword'] for kw in all_keywords)
        to_delete = all_keyword_names - keep_keywords
        
        if to_delete:
            self.db.delete_keywords(user_id, list(to_delete))
    
    def get_top_keywords_display(self, user_id: int) -> str:
        """Get formatted display of top keywords."""
        keywords = self.db.get_user_keywords(user_id, top_k=config.TOP_K * 2)
        
        if not keywords:
            return "You don't have any keywords yet. Like or dislike some jobs to build your profile!"
        
        positive = [kw for kw in keywords if not kw['is_negative']][:config.TOP_K]
        negative = [kw for kw in keywords if kw['is_negative']][:5]
        
        lines = ["🔑 *Your Top Keywords*\n"]
        
        if positive:
            lines.append("✅ *Positive:*")
            for kw in positive:
                emoji = "🔥" if kw['weight'] > 2.0 else "⭐"
                lines.append(f"{emoji} {kw['keyword']} (weight: {kw['weight']:.2f})")
        
        if negative:
            lines.append("\n❌ *Negative:*")
            for kw in negative:
                lines.append(f"🚫 {kw['keyword']} (weight: {kw['weight']:.2f})")
        
        return "\n".join(lines)


# Global manager instance
_manager = None

def get_keyword_manager() -> KeywordManager:
    """Get global keyword manager instance."""
    global _manager
    if _manager is None:
        _manager = KeywordManager()
    return _manager
