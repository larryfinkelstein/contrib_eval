"""
Unit tests for the evaluator logic in the contribution evaluation utility.
Covers edge cases and typical scenarios for Jira, Confluence, and GitHub data aggregation.
"""
import unittest
from evaluator import evaluate_contributions
from models import EvaluationResult

class MockJiraClient:
    def __init__(self, *args, **kwargs):
        # This mock constructor is intentionally left empty.
        # It is used for patching in unit tests and does not require initialization logic.
        pass
    def get_user_issues(self, user, start, end):
        return []

class MockConfluenceClient:
    def __init__(self, *args, **kwargs):
        # This mock constructor is intentionally left empty.
        # It is used for patching in unit tests and does not require initialization logic.
        pass
    def get_user_pages(self, user, start, end):
        return []

class MockGitHubClient:
    def __init__(self, *args, **kwargs):
        # This mock constructor is intentionally left empty.
        # It is used for patching in unit tests and does not require initialization logic.
        pass
    def get_user_contributions(self, user, start, end):
        return []

class TestEvaluator(unittest.TestCase):
    def setUp(self):
        # Patch evaluator to use mock clients
        import evaluator
        evaluator.JiraClient = MockJiraClient
        evaluator.ConfluenceClient = MockConfluenceClient
        evaluator.GitHubClient = MockGitHubClient

    def test_empty_contributions(self):
        """
        Test evaluation with no contributions (edge case).
        """
        result = evaluate_contributions(
            user="testuser",
            start_date="2025-01-01",
            end_date="2025-01-31",
            jira_project="TEST",
            confluence_space="SPACE",
            github_org="org",
            jira_token="dummy",
            confluence_token="dummy",
            github_token="dummy"
        )
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
        class MockJiraClient:
            def __init__(self, *args, **kwargs):
                # This mock constructor is intentionally left empty.
                # It is used for patching in unit tests and does not require initialization logic.
                pass
            def get_user_issues(self, user, start, end):
                return [{
                    'fields': {
                        'issuetype': {'name': 'Bug'},
                        'summary': 'Fix login issue',
                        'created': '2025-01-10',
                        'timespent': 7200
                    }
                }]
        class MockConfluenceClient:
            def __init__(self, *args, **kwargs):
                # This mock constructor is intentionally left empty.
                # It is used for patching in unit tests and does not require initialization logic.
                pass
            def get_user_pages(self, user, start, end):
                return [{
                    'title': 'API Documentation',
                    'history': {'createdDate': '2025-01-15', 'createdBy': {'username': user}},
                    'version': {'when': '2025-01-15'}
                }]
        class MockGitHubClient:
            def __init__(self, *args, **kwargs):
                # This mock constructor is intentionally left empty.
                # It is used for patching in unit tests and does not require initialization logic.
                pass
            def get_user_contributions(self, user, start, end):
                return [{
                    'pull_request': True,
                    'title': 'Add OAuth support',
                    'created_at': '2025-01-20'
                }]
        import evaluator
        evaluator.JiraClient = MockJiraClient
        evaluator.ConfluenceClient = MockConfluenceClient
        evaluator.GitHubClient = MockGitHubClient
        result = evaluate_contributions(
            user="testuser",
            start_date="2025-01-01",
            end_date="2025-01-31",
            jira_project="TEST",
            confluence_space="SPACE",
            github_org="org",
            jira_token="dummy",
            confluence_token="dummy",
            github_token="dummy"
        )
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
        class MockJiraClient:
            def __init__(self, *args, **kwargs):
                # This mock constructor is intentionally left empty.
                # It is used for patching in unit tests and does not require initialization logic.
                pass
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
        class MockConfluenceClient:
            def __init__(self, *args, **kwargs):
                # This mock constructor is intentionally left empty.
                # It is used for patching in unit tests and does not require initialization logic.
                pass
            def get_user_pages(self, user, start, end):
                return []
        class MockGitHubClient:
            def __init__(self, *args, **kwargs):
                # This mock constructor is intentionally left empty.
                # It is used for patching in unit tests and does not require initialization logic.
                pass
            def get_user_contributions(self, user, start, end):
                return [{
                    'issue': True,
                    'title': 'Bug: payment not processed',
                    'created_at': '2025-01-10'
                }]
        import evaluator
        evaluator.JiraClient = MockJiraClient
        evaluator.ConfluenceClient = MockConfluenceClient
        evaluator.GitHubClient = MockGitHubClient
        result = evaluate_contributions(
            user="testuser",
            start_date="2025-01-01",
            end_date="2025-01-31",
            jira_project="TEST",
            confluence_space="SPACE",
            github_org="org",
            jira_token="dummy",
            confluence_token="dummy",
            github_token="dummy"
        )
        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.involvement, 3)
        self.assertGreaterEqual(result.bugs_and_fixes, 2)
        self.assertGreaterEqual(result.complexity, 2)
        self.assertGreaterEqual(result.time_required, 5)

if __name__ == "__main__":
    unittest.main()
