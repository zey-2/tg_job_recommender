"""Keyword management and job scoring logic."""
import re
import json
import logging
from typing import List, Dict, Tuple
from collections import Counter
import config
from database import get_db
from llm_service import get_llm_service

# Configure logging
logger = logging.getLogger(__name__)


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
        job_id = job.get('id', 'N/A')
        
        # Tokenize job content
        title_tokens = self.tokenize(job.get('title', ''))
        desc_tokens = self.tokenize(job.get('description', ''))
        company_tokens = self.tokenize(
            job.get('company', {}).get('display_name', '') 
            if isinstance(job.get('company'), dict) 
            else str(job.get('company', ''))
        )
        # Parse skills, categories, MRT stations if available and add tokens
        skills = []
        try:
            skills = json.loads(job.get('skills_json') or '[]')
        except Exception:
            skills = []
        skill_tokens = []
        for s in skills:
            skill_tokens.extend(self.tokenize(s))

        categories = []
        try:
            categories = json.loads(job.get('category_json') or '[]')
        except Exception:
            categories = []
        cat_tokens = []
        for c in categories:
            cat_tokens.extend(self.tokenize(c))

        mrt = []
        try:
            mrt = json.loads(job.get('mrt_stations_json') or '[]')
        except Exception:
            mrt = []
        mrt_tokens = []
        for m in mrt:
            mrt_tokens.extend(self.tokenize(m))
        
        # Combine all tokens (include skills, categories, mrt)
        all_tokens = title_tokens + desc_tokens + company_tokens + skill_tokens + cat_tokens + mrt_tokens
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
                    logger.debug(f"[SCORE] Job {job_id} hard rejected due to negative keyword '{keyword}' (weight: {weight})")
                    return -1000.0, [keyword]
                
                # Soft negative - subtract weight
                if is_negative:
                    score -= abs(weight)
                    negative_match = True
                    logger.debug(f"[SCORE] Job {job_id} soft negative '{keyword}' (weight: {weight}, new score: {score})")
                else:
                    # Positive match - add weight
                    # Cap contribution to avoid single keyword dominance
                    contribution = min(weight, 5.0)
                    score += contribution
                    logger.debug(f"[SCORE] Job {job_id} positive match '{keyword}' (weight: {weight}, contribution: {contribution}, new score: {score})")
        
        # Penalty if only negative matches
        if negative_match and score <= 0:
            score -= 5.0
            logger.debug(f"[SCORE] Job {job_id} additional penalty for only negative matches (score: {score})")
        
        # Small boost for title matches (title is more important)
        title_match_bonus = sum(
            0.5 for kw_data in user_keywords 
            if kw_data['keyword'] in title_tokens and not kw_data['is_negative']
        )
        if title_match_bonus > 0:
            score += title_match_bonus
            logger.debug(f"[SCORE] Job {job_id} title match bonus: {title_match_bonus} (final score: {score})")

        # Skill exact match bonus (higher weight for explicit skills)
        skills_lower = [s.lower() for s in skills]
        for kw_data in user_keywords:
            kw = kw_data['keyword'].lower()
            if not kw_data['is_negative'] and kw in skills_lower and kw not in matched_keywords:
                score += 0.8
                matched_keywords.append(kw)
                logger.debug(f"[SCORE] Job {job_id} skills exact bonus for '{kw}' (+0.8) -> {score}")

        # Category match bonus
        categories_lower = [c.lower() for c in categories]
        for kw_data in user_keywords:
            kw = kw_data['keyword'].lower()
            if not kw_data['is_negative'] and kw in categories_lower and kw not in matched_keywords:
                score += 0.6
                matched_keywords.append(kw)
                logger.debug(f"[SCORE] Job {job_id} category bonus for '{kw}' (+0.6) -> {score}")
        
        final_score = max(score, 0.0)
        logger.debug(f"[SCORE] Job {job_id} final score: {final_score}, matched: {matched_keywords}")
        
        return final_score, matched_keywords
    
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
        logger.info(f"[RANK] Starting to rank {len(jobs)} jobs for user {user_id}")
        
        # Get user keywords
        user_keywords = self.db.get_user_keywords(user_id)
        logger.info(f"[RANK] User {user_id} has {len(user_keywords)} keywords")
        
        if not user_keywords:
            # No keywords yet - return jobs with neutral scoring
            logger.info(f"[RANK] No keywords for user {user_id}, returning all jobs with neutral score")
            return [(job, 1.0, []) for job in jobs]
        
        # Get recently shown jobs if needed
        recent_job_ids = set()
        if exclude_recent:
            recent_job_ids = set(self.db.get_recently_shown_jobs(user_id, days=7))
            logger.info(f"[RANK] User {user_id} has {len(recent_job_ids)} recently shown jobs (last 7 days)")
            if recent_job_ids:
                logger.debug(f"[RANK] Recent job IDs: {list(recent_job_ids)[:5]}... (showing first 5)")
        
        # Score and filter jobs
        scored_jobs = []
        excluded_count = 0
        negative_score_count = 0
        
        for job in jobs:
            job_id = job.get('id')
            job_title = job.get('title', 'N/A')
            
            # Skip recently shown jobs
            if job_id in recent_job_ids:
                excluded_count += 1
                logger.debug(f"[RANK] Excluding recently shown job: {job_id} - {job_title}")
                continue
            
            score, matched = self.score_job(job, user_keywords)
            
            # Skip jobs with negative scores (hard negatives)
            if score < 0:
                negative_score_count += 1
                logger.debug(f"[RANK] Excluding job with negative score: {job_id} - {job_title} (score: {score:.2f}, matched: {matched})")
                continue
            
            logger.debug(f"[RANK] Job {job_id} - {job_title} scored {score:.2f} (matched: {matched})")
            scored_jobs.append((job, score, matched))
        
        logger.info(f"[RANK] Results for user {user_id}: {len(scored_jobs)} jobs passed, "
                   f"{excluded_count} excluded (recent), {negative_score_count} excluded (negative score)")
        
        # Sort by score descending
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        
        if scored_jobs:
            logger.info(f"[RANK] Top 5 scores: {[(job.get('id'), score) for job, score, _ in scored_jobs[:5]]}")
        
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
        new_positive_added = 0
        new_negative_added = 0
        
        # Extract job info
        job_title = str(job.get('title', '') or '')
        company = job.get('company', {})
        if isinstance(company, dict):
            company = company.get('display_name', '')
        company = str(company or '')
        full_description = str(job.get('description', '') or '')
        description_preview = full_description[:500]
        
        job_tokens = set(self.tokenize(job_title))
        job_tokens.update(self.tokenize(company))
        job_tokens.update(self.tokenize(full_description))
        job_text_block = f"{job_title} {company} {full_description}".lower()
        
        if action in ('like', 'dislike') and job_tokens:
            direct_delta = config.LIKE_BOOST if action == 'like' else config.DISLIKE_PENALTY
            if direct_delta != 0:
                matched_existing = []
                for kw in current_keywords:
                    keyword_text = kw['keyword']
                    match = keyword_text in job_tokens
                    if not match and ' ' in keyword_text:
                        pattern = r'\b{}\b'.format(re.escape(keyword_text))
                        if re.search(pattern, job_text_block):
                            match = True
                    if match:
                        matched_existing.append(kw)
                for kw in matched_existing:
                    # Do not update weight for manual keywords - they have fixed weight
                    if kw.get('source') == 'manual':
                        logger.debug(f"Skipping weight update for manual keyword: {kw['keyword']}")
                        continue
                    self.db.update_keyword_weight(user_id, kw['keyword'], direct_delta)
                    kw['weight'] += direct_delta
                    kw['is_negative'] = kw['weight'] < config.NEGATIVE_PROMOTE_AT
        
        positive_count = sum(1 for kw in current_keywords if not kw['is_negative'])
        
        # Get LLM keyword suggestions
        # Extract skills array to provide context to the LLM
        try:
            skills = json.loads(job.get('skills_json') or '[]')
        except Exception:
            skills = []
        llm_suggestions = self.llm.expand_keywords(
            job_title=job_title,
            company=str(company),
            description=description_preview,
            current_keywords=current_keywords,
            user_reaction=action,
            skills=skills
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
                    delta = base_delta if base_delta <= 0 else -abs(base_delta)
                elif action == 'like' and sentiment == 'negative':
                    delta = -abs(base_delta) * 0.5  # Conflicting signal
                elif action == 'dislike' and sentiment == 'positive':
                    delta = base_delta * 0.5  # Conflicting signal
                else:
                    delta = 0.0
                
                new_weight = existing['weight'] + delta
                is_negative = new_weight < config.NEGATIVE_PROMOTE_AT
                
                # If existing keyword is manual, do not overwrite or change weight from LLM suggestions
                if existing.get('source') == 'manual':
                    logger.debug("Skipping LLM overwrite for manual keyword: %s", keyword)
                else:
                    self.db.upsert_keyword(
                        user_id=user_id,
                        keyword=keyword,
                        weight=new_weight,
                        is_negative=is_negative,
                        rationale=rationale,
                        source='auto'
                    )
                
                # Keep local copy in sync for subsequent iterations
                existing['weight'] = new_weight
                existing['is_negative'] = is_negative
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
                
                if not is_negative:
                    if positive_count >= config.TOP_K:
                        if new_positive_added >= config.MAX_NEW_POSITIVE_PER_FEEDBACK:
                            logger.debug(
                                "Skipping new keyword '%s' for user %s (limit reached)",
                                keyword,
                                user_id
                            )
                            continue
                        new_positive_added += 1
                    positive_count += 1
                else:
                    if new_negative_added >= config.MAX_NEW_NEGATIVE_PER_FEEDBACK:
                        logger.debug(
                            "Skipping new negative keyword '%s' for user %s (limit reached)",
                            keyword,
                            user_id
                        )
                        continue
                    new_negative_added += 1
                
                self.db.upsert_keyword(
                    user_id=user_id,
                    keyword=keyword,
                    weight=initial_weight,
                    is_negative=is_negative,
                    rationale=rationale,
                    source='auto'
                )
                current_keywords.append({
                    'keyword': keyword,
                    'weight': initial_weight,
                    'is_negative': is_negative,
                    'source': 'auto'
                })
        
        # Apply decay to all keywords
        self.db.decay_keywords(user_id, config.DECAY)
        
        # Prune low-weight keywords (keep top K positive + all active negatives)
        self._prune_keywords(user_id)
    
    def _prune_keywords(self, user_id: int):
        """Keep only top K keywords plus active negatives."""
        all_keywords = self.db.get_user_keywords(user_id)
        

        # Separate positive and negative
        positive_all = [kw for kw in all_keywords if not kw['is_negative']]
        negative = [kw for kw in all_keywords if kw['is_negative']]

        # Separate manual and auto positives
        manual_positive = [kw for kw in positive_all if kw.get('source') == 'manual']
        auto_positive = [kw for kw in positive_all if kw.get('source') != 'manual']

        # Keep most recent manual positives up to MAX_MANUAL_KEYWORDS
        manual_positive.sort(key=lambda x: x.get('updated_at') or x.get('created_at') or 0, reverse=True)
        keep_manual = manual_positive[:config.MAX_MANUAL_KEYWORDS]

        # Keep top auto positives up to the configured maximum (TOP_K - MAX_MANUAL_KEYWORDS)
        max_auto = max(config.TOP_K - config.MAX_MANUAL_KEYWORDS, 0)
        num_auto_keep = max_auto
        auto_positive.sort(key=lambda x: x['weight'], reverse=True)
        keep_auto = auto_positive[:num_auto_keep]
        
        # Keep all negatives with weight below threshold
        keep_negative = [kw for kw in negative if kw['weight'] < config.NEGATIVE_PROMOTE_AT]
        
        # Identify keywords to delete
        keep_keywords = set(kw['keyword'] for kw in keep_manual + keep_auto + keep_negative)
        all_keyword_names = set(kw['keyword'] for kw in all_keywords)
        to_delete = all_keyword_names - keep_keywords
        
        if to_delete:
            self.db.delete_keywords(user_id, list(to_delete))
    
    def get_top_keywords_display(self, user_id: int) -> str:
        """Get formatted display of top keywords."""
        keywords = self.db.get_user_keywords(user_id, top_k=config.TOP_K * 2)
        
        if not keywords:
            return "You don't have any keywords yet. Like or dislike some jobs to build your profile!"
        
        positive = [kw for kw in keywords if not kw['is_negative']]
        negative = [kw for kw in keywords if kw['is_negative']][:5]

        manual_positive = [kw for kw in positive if kw.get('source') == 'manual']
        auto_positive = [kw for kw in positive if kw.get('source') != 'manual']

        manual_count = len(manual_positive)
        auto_count = len(auto_positive)
        # Limit display counts per section
        manual_display = manual_positive[:config.MAX_MANUAL_KEYWORDS]
        auto_display = auto_positive[:max(config.TOP_K - config.MAX_MANUAL_KEYWORDS, config.TOP_K)]
        
        lines = ["🔑 *Your Top Keywords*\n"]
        
        if manual_display or auto_display:
            lines.append("✅ *Positive:*")
            if manual_display:
                lines.append(f"\n✍️ *Manual:* ({manual_count}/{config.MAX_MANUAL_KEYWORDS})")
                for kw in manual_display:
                    star_display = "⭐" * max(min(int(kw['weight'] / 0.5), 5), 1)
                    lines.append(f"{star_display} {kw['keyword']}")
            if auto_display:
                lines.append(f"\n🤖 *Auto:* ({auto_count}/{max(config.TOP_K - config.MAX_MANUAL_KEYWORDS, config.TOP_K)})")
                for kw in auto_display:
                # Use star rating instead of exact weight
                    stars = min(int(kw['weight'] / 0.5), 5)  # Max 5 stars
                    star_display = "⭐" * max(stars, 1)
                    lines.append(f"{star_display} {kw['keyword']}")
        
        if negative:
            lines.append("\n❌ *Negative:*")
            for kw in negative:
                lines.append(f"🚫 {kw['keyword']}")
        
        return "\n".join(lines)


# Global manager instance
_manager = None

def get_keyword_manager() -> KeywordManager:
    """Get global keyword manager instance."""
    global _manager
    if _manager is None:
        _manager = KeywordManager()
    return _manager
