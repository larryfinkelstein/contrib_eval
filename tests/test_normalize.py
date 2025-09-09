import unittest
from normalize.util import normalize_user, normalize_issue


class TestNormalize(unittest.TestCase):
    def test_normalize_user_minimal(self):
        raw = {'accountId': 'u123', 'displayName': 'Alice', 'emailAddress': 'a@example.com', 'login': 'alice'}
        user = normalize_user(raw)
        self.assertEqual(user.user_id, 'u123')
        self.assertEqual(user.display_name, 'Alice')
        self.assertIn('a@example.com', user.emails)
        self.assertIn('github', user.source_handles)

    def test_normalize_issue_jira(self):
        raw = {
            'id': '100',
            'key': 'PROJ-100',
            'fields': {
                'summary': 'Test issue',
                'issuetype': {'name': 'Bug'},
                'assignee': {'accountId': 'u123'},
                'created': '2025-01-01',
                'resolutiondate': '2025-01-02',
            },
        }
        issue = normalize_issue(raw)
        self.assertEqual(issue.issue_id, '100')
        self.assertEqual(issue.key, 'PROJ-100')
        self.assertEqual(issue.title, 'Test issue')
        self.assertEqual(issue.type, 'Bug')
        self.assertIn('u123', issue.assignees)


if __name__ == '__main__':
    unittest.main()
