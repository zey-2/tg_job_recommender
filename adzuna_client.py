"""Adzuna API client for job search."""
import requests
from typing import List, Dict, Optional
import config


class AdzunaClient:
    """Client for Adzuna Job Search API."""
    
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/sg/search"
    
    def __init__(self, app_id: str = None, app_key: str = None):
        """Initialize Adzuna client."""
        self.app_id = app_id or config.ADZUNA_APP_ID
        self.app_key = app_key or config.ADZUNA_APP_KEY
        
        if not self.app_id or not self.app_key:
            raise ValueError("Adzuna API credentials not configured")
    
    def search_jobs(self, 
                   keywords: List[str] = None,
                   where: str = "Singapore",
                   page: int = 1,
                   per_page: int = 25,
                   sort_by: str = "date",
                   salary_min: float = None,
                   max_days_old: int = 7) -> List[Dict]:
        """
        Search for jobs using Adzuna API.
        
        Args:
            keywords: List of keywords to search for
            where: Location to search in
            page: Page number (1-indexed)
            per_page: Results per page (max 50)
            sort_by: Sort order (date, relevance, salary)
            salary_min: Minimum salary filter
            max_days_old: Maximum age of job posting in days
            
        Returns:
            List of job dictionaries
        """
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": min(per_page, 50),
            "where": where,
            "sort_by": sort_by,
            "content-type": "application/json"
        }
        
        # Add keywords
        if keywords:
            params["what"] = " ".join(keywords)
        
        # Add optional filters
        if salary_min:
            params["salary_min"] = salary_min
        
        if max_days_old:
            params["max_days_old"] = max_days_old
        
        # Build URL
        url = f"{self.BASE_URL}/{page}"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching jobs from Adzuna: {e}")
            return []
    
    def search_by_keywords(self, keywords: List[str], limit: int = 25) -> List[Dict]:
        """
        Search jobs by user keywords.
        
        Args:
            keywords: List of keywords to search
            limit: Maximum number of results
            
        Returns:
            List of job dictionaries
        """
        return self.search_jobs(
            keywords=keywords,
            per_page=limit,
            sort_by="date"
        )
    
    def get_recent_jobs(self, limit: int = 50, max_days_old: int = 3) -> List[Dict]:
        """
        Get recent job postings.
        
        Args:
            limit: Maximum number of results
            max_days_old: Maximum age in days
            
        Returns:
            List of job dictionaries
        """
        return self.search_jobs(
            per_page=limit,
            max_days_old=max_days_old,
            sort_by="date"
        )
    
    def search_custom(self, query: str, limit: int = 25) -> List[Dict]:
        """
        Search jobs with custom query string.
        
        Args:
            query: Raw search query
            limit: Maximum number of results
            
        Returns:
            List of job dictionaries
        """
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": min(limit, 50),
            "what": query,
            "where": "Singapore",
            "sort_by": "relevance",
            "content-type": "application/json"
        }
        
        url = f"{self.BASE_URL}/1"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching jobs from Adzuna: {e}")
            return []


# Global client instance
_client = None

def get_adzuna_client() -> AdzunaClient:
    """Get global Adzuna client instance."""
    global _client
    if _client is None:
        _client = AdzunaClient()
    return _client
