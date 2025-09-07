"""
Evaluator logic for aggregating and scoring contributions.
"""
from typing import List
from jira_client import JiraClient
from confluence_client import ConfluenceClient
from github_client import GitHubClient
from models import Contribution, EvaluationResult


def convert_jira_issues_to_contributions(issues: List[dict]) -> List[Contribution]:
    """
    Convert Jira issues to Contribution objects.
    """
    contribs = []
    for issue in issues:
        issue_type = issue.get('fields', {}).get('issuetype', {}).get('name', 'Issue')
        description = issue.get('fields', {}).get('summary', '')
        date = issue.get('fields', {}).get('created', '')[:10]
        # Assign complexity based on issue type
        if issue_type.lower() == 'bug':
            complexity = 2
        elif issue_type.lower() == 'story':
            complexity = 5
        else:
            complexity = 3
        time_spent = issue.get('fields', {}).get('timespent', 0) / 3600 if issue.get('fields', {}).get('timespent') else 0.0
        bugs_reported = 1 if issue_type.lower() == 'bug' else 0
        contribs.append(Contribution('Jira', issue_type, description, date, complexity, time_spent, bugs_reported))
    return contribs


def convert_confluence_pages_to_contributions(pages: List[dict]) -> List[Contribution]:
    """
    Convert Confluence pages to Contribution objects.
    """
    contribs = []
    for page in pages:
        page_type = 'Page'
        description = page.get('title', '')
        date = page.get('history', {}).get('createdDate', '')[:10]
        complexity = 2  # Assume low complexity for documentation
        time_spent = 0.5  # Assume half hour per page
        bugs_reported = 0
        contribs.append(Contribution('Confluence', page_type, description, date, complexity, time_spent, bugs_reported))
    return contribs


def convert_github_items_to_contributions(items: List[dict]) -> List[Contribution]:
    """
    Convert GitHub items (PRs, commits, issues) to Contribution objects.
    """
    contribs = []
    for contrib in items:
        if 'pull_request' in contrib:
            contrib_type = 'Pull Request'
            description = contrib.get('title', '')
            date = contrib.get('created_at', '')[:10]
            complexity = 5  # Assume higher complexity for PRs
            time_spent = 2.0  # Assume 2 hours per PR
            bugs_reported = 0
        elif 'commit' in contrib:
            contrib_type = 'Commit'
            description = contrib.get('commit', {}).get('message', '')
            date = contrib.get('commit', {}).get('author', {}).get('date', '')[:10]
            complexity = 3
            time_spent = 1.0
            bugs_reported = 0
        else:
            contrib_type = 'Issue'
            description = contrib.get('title', '')
            date = contrib.get('created_at', '')[:10]
            complexity = 2
            time_spent = 0.5
            bugs_reported = 1 if 'bug' in description.lower() else 0
        contribs.append(Contribution('GitHub', contrib_type, description, date, complexity, time_spent, bugs_reported))
    return contribs


def calculate_metrics(contribs: List[Contribution]) -> EvaluationResult:
    """
    Calculate evaluation metrics from a list of contributions.
    """
    involvement = len(contribs)
    significance = sum(5 if c.type in ['Pull Request', 'Story'] else 2 for c in contribs) / (involvement or 1)
    effectiveness = sum(1 for c in contribs if c.bugs_reported == 0) / (involvement or 1)
    complexity = sum(c.complexity for c in contribs) / (involvement or 1)
    time_required = sum(c.time_spent for c in contribs)
    bugs_and_fixes = sum(c.bugs_reported for c in contribs)
    return EvaluationResult(
        involvement=involvement,
        significance=significance,
        effectiveness=effectiveness,
        complexity=complexity,
        time_required=time_required,
        bugs_and_fixes=bugs_and_fixes
    )


def evaluate_contributions(
    user: str,
    start_date: str,
    end_date: str,
    jira_project: str,
    confluence_space: str,
    github_org: str,
    jira_token: str,
    confluence_token: str,
    github_token: str
) -> EvaluationResult:
    """
    Aggregate contributions from Jira, Confluence, and GitHub, then evaluate metrics.

    Parameters:
        user (str): Username or email of the team member.
        start_date (str): Start date (YYYY-MM-DD).
        end_date (str): End date (YYYY-MM-DD).
        jira_project (str): Jira project key.
        confluence_space (str): Confluence space key.
        github_org (str): GitHub organization name.
        jira_token (str): Jira API token.
        confluence_token (str): Confluence API token.
        github_token (str): GitHub API token.

    Returns:
        EvaluationResult: Summary of the user's contributions.
    """
    jira = JiraClient(jira_token, jira_project)
    confluence = ConfluenceClient(confluence_token, confluence_space)
    github = GitHubClient(github_token, github_org)

    jira_contribs = convert_jira_issues_to_contributions(jira.get_user_issues(user, start_date, end_date))
    confluence_contribs = convert_confluence_pages_to_contributions(confluence.get_user_pages(user, start_date, end_date))
    github_contribs = convert_github_items_to_contributions(github.get_user_contributions(user, start_date, end_date))

    all_contribs: List[Contribution] = jira_contribs + confluence_contribs + github_contribs
    return calculate_metrics(all_contribs)
