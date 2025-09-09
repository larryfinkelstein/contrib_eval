"""
Simple Jira ingestion client used by the CLI/evaluator.
The implementations are lightweight: they return lists of dicts from the Jira REST API when credentials are provided,
but fall back to empty lists when tokens are missing to keep tests isolated.
"""

from typing import List, Dict, Any, Optional
import requests
from storage.cache import rate_limited_get, Cache


class JiraClient:
    """Minimal Jira client for fetching issues for a user within a date range.

    This class intentionally keeps network interaction simple so tests can mock methods.
    """

    def __init__(self, token: str, project_key: str, base_url: str = None, cache: Optional[Cache] = None):
        self.token = token
        self.project_key = project_key
        self.base_url = base_url or "https://your-jira-instance.atlassian.net/rest/api/3"
        self.headers = {
            "Authorization": f"Bearer {self.token}" if self.token else "",
            "Accept": "application/json",
        }
        self.cache = cache

    def get_user_issues(self, user: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Return a list of Jira issue dicts for the given user and date range.
        If no token is configured this returns an empty list (safe default for tests).
        """
        if not self.token:
            return []
        jql = f'project = {self.project_key} AND ' f'(assignee = "{user}" OR reporter = "{user}") AND ' f'created >= "{start_date}" AND created <= "{end_date}"'
        url = f"{self.base_url}/search"
        issues: List[Dict[str, Any]] = []
        start_at = 0
        max_results = 50
        while True:
            params = {"jql": jql, "startAt": start_at, "maxResults": max_results}
            if self.cache:
                key = f"jira:{self.project_key}:{user}:{start_at}:{start_date}:{end_date}"
                res = rate_limited_get(url, headers=self.headers, params=params, cache=self.cache, cache_key=key)
                status = res.get('status', 500)
                data = res.get('response', {})
            else:
                resp = requests.get(url, headers=self.headers, params=params)
                status = resp.status_code
                data = resp.json() if status == 200 else {}
            if status != 200:
                break
            issues.extend(data.get('issues', []))
            if len(data.get('issues', [])) < max_results:
                break
            start_at += max_results
        return issues
