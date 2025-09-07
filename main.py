"""
Main entry point for the contribution evaluation utility.
Handles argument parsing and orchestrates data collection and evaluation.
"""

import argparse
import os
from evaluator import evaluate_contributions


def env_or_prompt(env_var: str, prompt_text: str) -> str:
    """
    Returns the value from the environment variable if set,
    otherwise prompts the user for input.
    """
    value = os.environ.get(env_var)
    if value:
        return value
    return input(f"{prompt_text}: ")


def main():
    """
    Parse command-line arguments and run the evaluation.
    """
    parser = argparse.ArgumentParser(description="Evaluate team member contributions.")
    parser.add_argument('--user', required=True, help='Team member username/email')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--jira_project', required=False, default='MCLD', help='Jira project key (default: MCLD)')
    parser.add_argument('--confluence_space', required=False, default='SMARTINT', help='Confluence space key (default: SMARTINT)')
    parser.add_argument('--github_org', required=False, default='comcast-mesh', help='GitHub organization name (default: comcast-mesh)')
    parser.add_argument('--jira_token', required=True, type=lambda v: v or env_or_prompt('JIRA_TOKEN', 'Enter Jira API token'), default=None, help='Jira API token (or set JIRA_TOKEN env var)')
    parser.add_argument('--confluence_token', required=True, type=lambda v: v or env_or_prompt('CONFLUENCE_TOKEN', 'Enter Confluence API token'), default=None, help='Confluence API token (or set CONFLUENCE_TOKEN env var)')
    parser.add_argument('--github_token', required=True, type=lambda v: v or env_or_prompt('GITHUB_TOKEN', 'Enter GitHub API token'), default=None, help='GitHub API token (or set GITHUB_TOKEN env var)')
    args = parser.parse_args()

    results = evaluate_contributions(
        user=args.user,
        start_date=args.start,
        end_date=args.end,
        jira_project=args.jira_project,
        confluence_space=args.confluence_space,
        github_org=args.github_org,
        jira_token=args.jira_token,
        confluence_token=args.confluence_token,
        github_token=args.github_token
    )
    print(results)


if __name__ == "__main__":
    main()
