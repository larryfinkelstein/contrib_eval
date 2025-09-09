"""
Confluence ingestion module: pulls pages, comments.
"""

from typing import List, Dict, Any, Optional
import requests
from storage.cache import rate_limited_get, Cache


class ConfluenceClient:
    """
    Client for interacting with Confluence API to fetch user contributions.
    """

    def __init__(self, token: str, space_key: str, base_url: str = None, cache: Optional[Cache] = None):
        self.token = token
        self.space_key = space_key
        self.base_url = base_url or "https://your-confluence-instance.atlassian.net/wiki/rest/api"
        self.headers = {"Authorization": f"Bearer {self.token}" if self.token else "", "Accept": "application/json"}
        self.cache = cache

    def get_user_pages(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Return a list of Confluence page dicts for the given user and date range.
        If no token is configured this returns an empty list (safe default for tests).
        """
        if not self.token:
            return []
        url = f"{self.base_url}/content"
        pages: List[Dict[str, Any]] = []
        start = 0
        limit = 50
        while True:
            params = {"spaceKey": self.space_key, "limit": limit, "start": start, "expand": "version,history"}
            if self.cache:
                key = f"confluence:{self.space_key}:{start}:{start_date}:{end_date}"
                res = rate_limited_get(url, headers=self.headers, params=params, cache=self.cache, cache_key=key)
                status = res.get('status', 500)
                data = res.get('response', {})
            else:
                resp = requests.get(url, headers=self.headers, params=params)
                status = resp.status_code
                data = resp.json() if status == 200 else {}
            if status != 200:
                break
            pages.extend(data.get('results', []))
            if len(data.get('results', [])) < limit:
                break
            start += limit
        return pages
