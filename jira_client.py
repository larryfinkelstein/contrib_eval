"""
Jira API client for fetching user contributions.
"""
from typing import List, Dict
import requests

class JiraClient:
    """
    Client for interacting with Jira API to fetch user contributions.
    """
    def __init__(self, token: str, project_key: str):
        """
        Initialize Jira client with API token and project key.

        Parameters:
            token (str): Jira API token.
            project_key (str): Jira project key.
        """
        self.token = token
        self.project_key = project_key
        self.base_url = "https://your-jira-instance.atlassian.net/rest/api/3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

    def get_user_issues(self, user: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch issues assigned to or reported by the user in the project within the date range.
        Handles pagination and returns a list of issue dicts.

        Parameters:
            user (str): Username or email of the team member.
            start_date (str): Start date (YYYY-MM-DD).
            end_date (str): End date (YYYY-MM-DD).

        Returns:
            List[Dict]: List of issues.
        """
        jql = (
            f'project = {self.project_key} AND '
            f'(assignee = "{user}" OR reporter = "{user}") AND '
            f'created >= "{start_date}" AND created <= "{end_date}"'
        )
        url = f"{self.base_url}/search"
        issues = []
        start_at = 0
        max_results = 50
        while True:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results
            }
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                # Log error and break
                break
            data = response.json()
            issues.extend(data.get("issues", []))
            if start_at + max_results >= data.get("total", 0):
                break
            start_at += max_results
        return issues
