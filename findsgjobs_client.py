"""FindSGJobs API client for job search.
"""
import requests
import logging
import json
from typing import List, Dict, Optional
import config
from database import get_db

logger = logging.getLogger(__name__)


class FindSGJobsClient:
    """Client for FindSGJobs API.
    Provides a similar interface to the Adzuna client previously used.
    """

    BASE_URL = config.FINDSGJOBS_API_ENDPOINT
    RATE_LIMIT_MAX = 60  # requests per minute
    RATE_LIMIT_WINDOW = 60  # seconds
    DEFAULT_PER_PAGE_COUNT = 100

    def __init__(self):
        self.endpoint = config.FINDSGJOBS_API_ENDPOINT
        self.use_searchable = config.FINDSGJOBS_USE_SEARCHABLE
        self._redirect_url_validated = False
        self.db = get_db()

    def _validate_redirect_url(self):
        """Check if the API endpoint returns a 'redirect_url' in job items.
        This is done only once and cached for the session.
        """
        if self._redirect_url_validated:
            return
        logger.info("[FINDSGJOBS] Validating whether redirect_url exists in API response")
        # Use a larger per_page_count when validating to better observe fields like redirect_url
        params = {"per_page_count": self.DEFAULT_PER_PAGE_COUNT, "page": 1}
        try:
            resp = requests.get(self.endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = (data.get("data", {}).get("result") or [])
            has_redirect = False
            if results:
                job = results[0].get('job', {})
                if 'redirect_url' in job:
                    has_redirect = True
            self._redirect_url_validated = True
            self._redirect_has_redirect_url = has_redirect
            logger.info(f"[FINDSGJOBS] redirect_url present: {has_redirect}")
        except Exception as e:
            logger.warning(f"[FINDSGJOBS] redirect_url validation failed: {e}")
            # Assume False, but cache check as done
            self._redirect_url_validated = True
            self._redirect_has_redirect_url = False

    def _construct_job_url(self, job: Dict) -> str:
        """Construct a job URL: prefer redirect_url if provided otherwise construct from id/sid."""
        if job.get('redirect_url'):
            return job.get('redirect_url')
        job_id = job.get('id') or job.get('sid')
        if not job_id:
            return ''
        return f"https://www.findsgjobs.com/job/{job_id}"

    def _normalize_job(self, item: Dict) -> Dict:
        """Normalize FindSGJobs item to simplified job dict for bot/storage."""
        job = item.get('job', {})
        company = item.get('company', {})

        # Normalize skills array to flat strings
        raw_skills = job.get('id_Job_Skills') or []
        skills = []
        for s in raw_skills:
            if isinstance(s, str):
                skills.append(s)
            elif isinstance(s, dict):
                caption = s.get('caption') or s.get('name') or ''
                if caption:
                    skills.append(caption)
            else:
                skills.append(str(s))

        # Extract categories, employment types, mrt stations, timing shifts
        categories = [c.get('caption') for c in job.get('JobCategory', []) if isinstance(c, dict) and c.get('caption')]
        employment_types = [e.get('caption') for e in job.get('EmploymentType', []) if isinstance(e, dict) and e.get('caption')]
        mrt_stations = [m.get('caption') for m in job.get('id_Job_NearestMRTStation', []) if isinstance(m, dict) and m.get('caption')]
        timing_shifts = [t.get('caption') for t in job.get('id_Job_TimingShift', []) if isinstance(t, dict) and t.get('caption')]

        # Salary fields
        salary_display_text = job.get('Salaryrange', {}).get('caption') if isinstance(job.get('Salaryrange'), dict) else None
        salary_currency = (job.get('id_Job_Currency') or {}).get('caption') if isinstance(job.get('id_Job_Currency'), dict) else None
        salary_interval = (job.get('id_Job_Interval') or {}).get('caption') if isinstance(job.get('id_Job_Interval'), dict) else None

        normalized = {
            'id': str(job.get('id') or job.get('sid') or ''),
            'title': job.get('Title'),
            'company': {'display_name': company.get('CompanyName')} if company else job.get('CompanyName'),
            'location': {'display_name': ', '.join(mrt_stations) if mrt_stations else 'Singapore'},
            'description': job.get('JobDescription'),
            'url': self._construct_job_url(job),
            'salary_min': job.get('id_Job_Salary'),
            'salary_max': job.get('id_Job_MaxSalary'),
            'salary_currency': salary_currency,
            'salary_interval': salary_interval,
            'salary_display_text': salary_display_text,
            'salary_hidden': job.get('id_Job_Donotdisplaysalary', 0),
            'category_json': json.dumps(categories),
            'employment_type_json': json.dumps(employment_types),
            'mrt_stations_json': json.dumps(mrt_stations),
            'skills_json': json.dumps(skills),
            'position_level': (job.get('id_Job_PositionLevel') or {}).get('caption') if job.get('id_Job_PositionLevel') else None,
            'experience_required': (job.get('MinimumYearsofExperience') or {}).get('caption') if job.get('MinimumYearsofExperience') else None,
            'education_required': (job.get('MinimumEducationLevel') or {}).get('caption') if job.get('MinimumEducationLevel') else None,
            'timing_shift_json': json.dumps(timing_shifts),
            'activation_date': job.get('activation_date'),
            'expiration_date': job.get('expiration_date'),
            'created': job.get('activation_date') or job.get('created'),
            'raw_job': json.dumps(job)
        }
        return normalized

    def _make_request(self, params: Dict, context=None) -> List[Dict]:
        """Make a GET request to FindSGJobs with rate limiting and endpoint validation.
        If rate limited, `wait_for_rate_limit` returns wait time (seconds), which gets reported to user via provided context.
        """
        # Rate limit
        wait_seconds = self.db.wait_for_rate_limit('findsgjobs', self.RATE_LIMIT_MAX, self.RATE_LIMIT_WINDOW)
        if wait_seconds:
            try:
                if context:
                    # notify user that we're waiting due to rate limit
                    chat_id = getattr(context, 'chat_id', None) or getattr(context, '_chat_id', None)
                    if chat_id is None:
                        # Try to obtain a chat_id from callback_data style context
                        chat_id = getattr(context, 'user_id', None)
                    if chat_id is not None:
                        try:
                            import asyncio
                            if asyncio.get_event_loop().is_running():
                                # Schedule message sending without blocking
                                asyncio.create_task(
                                    context.bot.send_message(chat_id=chat_id, text=f"⚠️ Rate limit reached, waiting {int(wait_seconds)}s to continue..."))
                            else:
                                # Synchronous fallback (may not run in async contexts)
                                context.bot.send_message(chat_id=chat_id, text=f"⚠️ Rate limit reached, waiting {int(wait_seconds)}s to continue...")
                        except Exception:
                            # Last-resort approach: use non-awaited call
                            try:
                                context.bot.send_message(chat_id=chat_id, text=f"⚠️ Rate limit reached, waiting {int(wait_seconds)}s to continue...")
                            except Exception:
                                pass
                # Sleep for the wait time, then re-check/consume a slot
                import time
                time.sleep(wait_seconds)
                # After sleeping, try to register the new request (should succeed)
                self.db.wait_for_rate_limit('findsgjobs', self.RATE_LIMIT_MAX, self.RATE_LIMIT_WINDOW)
            except Exception:
                # Silently continue if we couldn't notify or wait
                pass

        # Validate redirect_url only once per session
        if not getattr(self, '_redirect_url_validated', False):
            self._validate_redirect_url()

        try:
            logger.info(f"[FINDSGJOBS] Requesting jobs from {self.endpoint} params={params}")
            resp = requests.get(self.endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get('data', {}).get('result', [])
            # If we previously checked and endpoint was supposed to have redirect_url but missing -> log
            if getattr(self, '_redirect_has_redirect_url', False):
                # check and warn if missing in this response
                if results and not results[0].get('job', {}).get('redirect_url'):
                    logger.warning("[FINDSGJOBS] Expected redirect_url but it is missing from job item")
            # Normalize jobs
            normalized_jobs = [self._normalize_job(item) for item in results]
            # Filter out blocklisted companies (case-insensitive) defined in config.COMPANY_BLOCKLIST
            try:
                blocklist = {b.strip().upper() for b in getattr(config, 'COMPANY_BLOCKLIST', []) if b}
            except Exception:
                blocklist = set()

            def _company_display_name_from_norm(job_item: Dict) -> str:
                comp = job_item.get('company')
                if isinstance(comp, dict):
                    return (comp.get('display_name') or '').strip().upper()
                if isinstance(comp, str):
                    return comp.strip().upper()
                return ''

            if blocklist:
                before = len(normalized_jobs)
                normalized_jobs = [j for j in normalized_jobs if _company_display_name_from_norm(j) not in blocklist]
                after = len(normalized_jobs)
                if before != after:
                    logger.info(f"[FINDSGJOBS] Filtered out {before-after} jobs due to company blocklist")

            return normalized_jobs
        except requests.exceptions.RequestException as e:
            logger.error(f"[FINDSGJOBS] Error fetching jobs: {e}")
            return []

    def search_jobs(self, keywords: str = '', min_salary: Optional[int] = None, page: int = 1, per_page_count: int = DEFAULT_PER_PAGE_COUNT, sort_field: str = 'activation_date', sort_direction: str = 'desc', context=None) -> List[Dict]:
        params = {
            'page': page,
            'per_page_count': per_page_count,
            'sort_field': sort_field,
            'sort_direction': sort_direction
        }
        if keywords:
            params['keywords'] = keywords
        # Only apply monthly min salary filter per requirements
        if min_salary is not None:
            params['id_Job_Salary'] = min_salary
            params['id_Job_Currency'] = config.CURRENCIES.get('SGD')
            params['id_Job_Interval'] = config.SALARY_INTERVALS.get('month')

        return self._make_request(params, context=context)

    def search_by_keywords(self, keywords: List[str], limit: int = 50, user_id: int = None, context=None) -> List[Dict]:
        kw = ' '.join(keywords) if isinstance(keywords, list) else keywords
        min_salary = None
        if user_id:
            user = self.db.get_user(user_id)
            min_salary = user.get('min_salary_preference') if user else None
        # Ensure we request a meaningful page size (at least DEFAULT_PER_PAGE_COUNT) to fetch more candidates
        # Request more candidates (double the requested limit) to account for any filtered/blocklisted jobs
        per_page = max(limit * 2, self.DEFAULT_PER_PAGE_COUNT) if (limit is not None) else self.DEFAULT_PER_PAGE_COUNT
        return self.search_jobs(keywords=kw, min_salary=min_salary, per_page_count=per_page, context=context)

    def get_recent_jobs(self, limit: int = 100, user_id: int = None, context=None) -> List[Dict]:
        min_salary = None
        if user_id:
            user = self.db.get_user(user_id)
            min_salary = user.get('min_salary_preference') if user else None
        # Request more candidates (double the requested limit) to account for any filtered/blocklisted jobs
        per_page = max(limit * 2, self.DEFAULT_PER_PAGE_COUNT) if (limit is not None) else self.DEFAULT_PER_PAGE_COUNT
        return self.search_jobs(keywords='', min_salary=min_salary, per_page_count=per_page, context=context)

    def search_custom(self, query: str, limit: int = 100, user_id: int = None, context=None) -> List[Dict]:
        min_salary = None
        if user_id:
            user = self.db.get_user(user_id)
            min_salary = user.get('min_salary_preference') if user else None
        # Request more candidates (double the requested limit) to account for any filtered/blocklisted jobs
        per_page = max(limit * 2, self.DEFAULT_PER_PAGE_COUNT) if (limit is not None) else self.DEFAULT_PER_PAGE_COUNT
        return self.search_jobs(keywords=query, min_salary=min_salary, per_page_count=per_page, context=context)


# Global singleton
_client = None

def get_findsgjobs_client() -> FindSGJobsClient:
    global _client
    if _client is None:
        _client = FindSGJobsClient()
    return _client
