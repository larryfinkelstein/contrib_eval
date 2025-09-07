"""
GitHub API client for fetching user contributions.
"""
from typing import List, Dict
import requests

class GitHubClient:
    """
    Client for interacting with GitHub API to fetch user contributions.
    """
    def __init__(self, token: str, org: str):
        """
        Initialize GitHub client with personal access token and organization name.

        Parameters:
            token (str): GitHub personal access token.
            org (str): GitHub organization name.
        """
        self.token = token
        self.org = org
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json"
        }

    def _fetch_repos(self, per_page: int = 50) -> List[Dict]:
        """
        Fetch all repositories in the organization.
        """
        repos_url = f"{self.base_url}/orgs/{self.org}/repos"
        page = 1
        repos = []
        while True:
            params = {"page": page, "per_page": per_page}
            resp = requests.get(repos_url, headers=self.headers, params=params)
            if resp.status_code != 200:
                break
            data = resp.json()
            repos.extend(data)
            if len(data) < per_page:
                break
            page += 1
        return repos

    def _fetch_prs(self, repo_name: str, per_page: int = 50) -> List[Dict]:
        """
        Fetch all pull requests for a repository.
        """
        pr_url = f"{self.base_url}/repos/{self.org}/{repo_name}/pulls"
        pr_params = {"state": "all", "per_page": per_page}
        pr_resp = requests.get(pr_url, headers=self.headers, params=pr_params)
        return pr_resp.json() if pr_resp.status_code == 200 else []

    def _fetch_issues(self, repo_name: str, per_page: int = 50) -> List[Dict]:
        """
        Fetch all issues for a repository.
        """
        issues_url = f"{self.base_url}/repos/{self.org}/{repo_name}/issues"
        issues_params = {"state": "all", "per_page": per_page}
        issues_resp = requests.get(issues_url, headers=self.headers, params=issues_params)
        return issues_resp.json() if issues_resp.status_code == 200 else []

    def _fetch_commits(self, repo_name: str, user: str, start_date: str, end_date: str, per_page: int = 50) -> List[Dict]:
        """
        Fetch all commits by a user for a repository in a date range.
        """
        commits_url = f"{self.base_url}/repos/{self.org}/{repo_name}/commits"
        commits_params = {"author": user, "since": start_date, "until": end_date, "per_page": per_page}
        commits_resp = requests.get(commits_url, headers=self.headers, params=commits_params)
        return commits_resp.json() if commits_resp.status_code == 200 else []

    def _filter_by_user_and_date(self, items: List[Dict], user: str, start_date: str, end_date: str, date_field: str = "created_at") -> List[Dict]:
        """
        Filter items by user and date range.
        """
        filtered = []
        for item in items:
            login = item.get("user", {}).get("login", "")
            created_at = item.get(date_field, "")[:10]
            if login == user and start_date <= created_at <= end_date:
                filtered.append(item)
        return filtered

    def get_user_contributions(self, user: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch PRs, commits, and issues by the user in the org within the date range.
        Handles pagination and returns a list of contribution dicts.
        """
        contributions = []
        repos = self._fetch_repos()
        for repo in repos:
            repo_name = repo["name"]
            prs = self._fetch_prs(repo_name)
            contributions.extend(self._filter_by_user_and_date(prs, user, start_date, end_date, "created_at"))
            issues = self._fetch_issues(repo_name)
            contributions.extend(self._filter_by_user_and_date(issues, user, start_date, end_date, "created_at"))
            commits = self._fetch_commits(repo_name, user, start_date, end_date)
            contributions.extend(commits)
        return contributions
