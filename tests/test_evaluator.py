"""
Unit tests for the evaluator logic in the contribution evaluation utility.
Covers edge cases and typical scenarios for Jira, Confluence, and GitHub data aggregation.
"""
import unittest
from scoring.metrics import (
    convert_jira_issues_to_events,
    convert_confluence_pages_to_events,
    convert_github_items_to_events,
    compute_metrics,
)
from correlate.models import EvaluationResult


class MockJiraClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_user_issues(self, user, start, end):
        return []


class MockConfluenceClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_user_pages(self, user, start, end):
        return []


class MockGitHubClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_user_contributions(self, user, start, end):
        return []


class TestEvaluator(unittest.TestCase):
    def test_empty_contributions(self):
        """
        Test evaluation with no contributions (edge case).
        """
        jira = MockJiraClient()
        conf = MockConfluenceClient()
        gh = MockGitHubClient()

        jira_raw = jira.get_user_issues("testuser", "2025-01-01", "2025-01-31")
        conf_raw = conf.get_user_pages("testuser", "2025-01-01", "2025-01-31")
        gh_raw = gh.get_user_contributions("testuser", "2025-01-01", "2025-01-31")

        events = (
            convert_jira_issues_to_events(jira_raw)
            + convert_confluence_pages_to_events(conf_raw)
            + convert_github_items_to_events(gh_raw)
        )
        res = compute_metrics(events)
        result = res.get('evaluation_result')

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.involvement, 0)
        self.assertEqual(result.significance, 0)
        self.assertEqual(result.effectiveness, 0)
        self.assertEqual(result.complexity, 0)
        self.assertEqual(result.time_required, 0)
        self.assertEqual(result.bugs_and_fixes, 0)

    def test_mixed_contributions(self):
        """
        Test evaluation with mixed contributions from all sources.
        """
        class MockJiraClientLocal:
            def get_user_issues(self, user, start, end):
                return [{
                    'fields': {
                        'issuetype': {'name': 'Bug'},
                        'summary': 'Fix login issue',
                        'created': '2025-01-10',
                        'timespent': 7200
                    }
                }]

        class MockConfluenceClientLocal:
            def get_user_pages(self, user, start, end):
                return [{
                    'title': 'API Documentation',
                    'history': {'createdDate': '2025-01-15', 'createdBy': {'username': user}},
                    'version': {'when': '2025-01-15'}
                }]

        class MockGitHubClientLocal:
            def get_user_contributions(self, user, start, end):
                return [{
                    'pull_request': True,
                    'title': 'Add OAuth support',
                    'created_at': '2025-01-20'
                }]

        jira = MockJiraClientLocal()
        conf = MockConfluenceClientLocal()
        gh = MockGitHubClientLocal()

        events = (
            convert_jira_issues_to_events(jira.get_user_issues(None, None, None))
            + convert_confluence_pages_to_events(conf.get_user_pages(None, None, None))
            + convert_github_items_to_events(gh.get_user_contributions(None, None, None))
        )
        res = compute_metrics(events)
        result = res.get('evaluation_result')

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.involvement, 3)
        self.assertGreater(result.significance, 0)
        self.assertGreater(result.complexity, 0)
        self.assertGreater(result.time_required, 0)
        self.assertEqual(result.bugs_and_fixes, 1)

    def test_high_complexity_and_bugs(self):
        """
        Test evaluation with high complexity and multiple bugs.
        """
        class MockJiraClientLocal:
            def get_user_issues(self, user, start, end):
                return [{
                    'fields': {
                        'issuetype': {'name': 'Story'},
                        'summary': 'Implement payment gateway',
                        'created': '2025-01-05',
                        'timespent': 14400
                    }
                }, {
                    'fields': {
                        'issuetype': {'name': 'Bug'},
                        'summary': 'Fix checkout bug',
                        'created': '2025-01-07',
                        'timespent': 3600
                    }
                }]

        class MockConfluenceClientLocal:
            def get_user_pages(self, user, start, end):
                return []

        class MockGitHubClientLocal:
            def get_user_contributions(self, user, start, end):
                return [{
                    'issue': True,
                    'title': 'Bug: payment not processed',
                    'created_at': '2025-01-10'
                }]

        jira = MockJiraClientLocal()
        conf = MockConfluenceClientLocal()
        gh = MockGitHubClientLocal()

        events = (
            convert_jira_issues_to_events(jira.get_user_issues(None, None, None))
            + convert_confluence_pages_to_events(conf.get_user_pages(None, None, None))
            + convert_github_items_to_events(gh.get_user_contributions(None, None, None))
        )
        res = compute_metrics(events)
        result = res.get('evaluation_result')

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.involvement, 3)
        self.assertGreaterEqual(result.bugs_and_fixes, 2)
        self.assertGreaterEqual(result.complexity, 2)
        self.assertGreaterEqual(result.time_required, 5)


if __name__ == "__main__":
    unittest.main()
