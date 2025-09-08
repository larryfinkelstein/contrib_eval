"""
Minimal GitHub ingestion client used by evaluator and tests.
Provides a safe default (empty lists) when no token is supplied to keep tests deterministic.
"""
from typing import List, Dict, Any, Optional
import requests
from storage.cache import rate_limited_get, Cache


class GitHubClient:
    """Simple GitHub client to fetch repositories, PRs, and user contributions."""

    def __init__(self, token: str, org: str, base_url: str = None, cache: Optional[Cache] = None):
        self.token = token
        self.org = org
        self.base_url = base_url or "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}" if self.token else "",
            "Accept": "application/vnd.github+json",
        }
        self.cache = cache

    def _fetch_repos(self, per_page: int = 50) -> List[Dict[str, Any]]:
        if not self.token:
            return []
        repos_url = f"{self.base_url}/orgs/{self.org}/repos"
        page = 1
        repos: List[Dict[str, Any]] = []
        while True:
            params = {"page": page, "per_page": per_page}
            if self.cache:
                key = f"github:repos:{self.org}:page:{page}:per:{per_page}"
                res = rate_limited_get(repos_url, headers=self.headers, params=params, cache=self.cache, cache_key=key)
                status = res.get('status', 500)
                data = res.get('response', {})
            else:
                resp = requests.get(repos_url, headers=self.headers, params=params)
                status = resp.status_code
                data = resp.json() if status == 200 else {}
            if status != 200:
                break
            repos.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return repos

    def _fetch_prs(self, repo_name: str, per_page: int = 50) -> List[Dict[str, Any]]:
        if not self.token:
            return []
        pr_url = f"{self.base_url}/repos/{self.org}/{repo_name}/pulls"
        page = 1
        prs: List[Dict[str, Any]] = []
        while True:
            params = {"page": page, "per_page": per_page, "state": "all"}
            if self.cache:
                key = f"github:prs:{self.org}:{repo_name}:page:{page}:per:{per_page}"
                res = rate_limited_get(pr_url, headers=self.headers, params=params, cache=self.cache, cache_key=key)
                status = res.get('status', 500)
                data = res.get('response', {})
            else:
                resp = requests.get(pr_url, headers=self.headers, params=params)
                status = resp.status_code
                data = resp.json() if status == 200 else {}
            if status != 200:
                break
            prs.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return prs

    def _pr_passes_filters(self, pr: Dict[str, Any], user: str, start_date: str = None, end_date: str = None) -> bool:
        author = (pr.get('user') or {}).get('login')
        if not author:
            return False
        if author.lower() != user.lower():
            return False
        created = pr.get('created_at') or pr.get('updated_at')
        if start_date and created and created < start_date:
            return False
        if end_date and created and created > end_date:
            return False
        return True

    def _gather_prs_for_repo(self, repo_name: str, user: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        matched: List[Dict[str, Any]] = []
        for pr in self._fetch_prs(repo_name):
            if self._pr_passes_filters(pr, user, start_date, end_date):
                pr['_repo_name'] = repo_name
                matched.append(pr)
        return matched

    def get_user_prs(self, user: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Aggregate PRs across org repos authored by the given user. Date filters are optional and applied client-side if provided."""
        if not self.token:
            return []
        prs: List[Dict[str, Any]] = []
        repos = self._fetch_repos()
        for r in repos:
            name = r.get('name')
            if not name:
                continue
            prs.extend(self._gather_prs_for_repo(name, user, start_date, end_date))
        return prs

    def get_user_contributions(self, user: str, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """Convenience method used by evaluator/tests: returns PRs and other contributions.
        For now we return PR objects which are sufficient for scoring heuristics.
        """
        return self.get_user_prs(user, start_date, end_date)
