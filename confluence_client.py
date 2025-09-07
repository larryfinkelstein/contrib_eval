"""
Confluence API client for fetching user contributions.
"""
from typing import List, Dict
import requests

class ConfluenceClient:
    """
    Client for interacting with Confluence API to fetch user contributions.
    """
    def __init__(self, token: str, space_key: str):
        """
        Initialize Confluence client with API token and space key.

        Parameters:
            token (str): Confluence API token.
            space_key (str): Confluence space key.
        """
        self.token = token
        self.space_key = space_key
        self.base_url = "https://your-confluence-instance.atlassian.net/wiki/rest/api"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

    def get_user_pages(self, user: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch pages created or updated by the user in the space within the date range.
        Handles pagination and returns a list of page dicts.

        Parameters:
            user (str): Username or email of the team member.
            start_date (str): Start date (YYYY-MM-DD).
            end_date (str): End date (YYYY-MM-DD).

        Returns:
            List[Dict]: List of pages.
        """
        url = f"{self.base_url}/content"
        pages = []
        start = 0
        limit = 50
        while True:
            params = {
                "spaceKey": self.space_key,
                "limit": limit,
                "start": start,
                "expand": "version,history"
            }
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                # Log error and break
                break
            data = response.json()
            for page in data.get("results", []):
                # Filter by user and date
                creator = page.get("history", {}).get("createdBy", {}).get("username", "")
                created_date = page.get("history", {}).get("createdDate", "")[:10]
                last_updated = page.get("version", {}).get("when", "")[:10]
                if (creator == user and start_date <= created_date <= end_date) or \
                   (creator == user and start_date <= last_updated <= end_date):
                    pages.append(page)
            if not data.get("_links", {}).get("next"):
                break
            start += limit
        return pages
