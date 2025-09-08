import unittest
from correlate.linker import find_issue_keys_in_text, link_events_to_issues

class TestLinker(unittest.TestCase):
    def test_find_keys(self):
        text = "Fixed PROJ-123 and addressed PROJ-456 in this change"
        keys = find_issue_keys_in_text(text)
        self.assertIn('PROJ-123', keys)
        self.assertIn('PROJ-456', keys)

    def test_link_events_to_issues(self):
        events = [
            {'id': 'evt1', 'title': 'Related to PROJ-1', 'metadata': {'comment': 'see PROJ-1'}},
            {'id': 'evt2', 'body': 'No keys here'},
        ]
        issues = [{'key': 'PROJ-1'}, {'key': 'OTHER-2'}]
        links = link_events_to_issues(events, issues)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].bug_issue_id, 'PROJ-1')
        self.assertEqual(links[0].origin_issue_id, 'evt1')

if __name__ == '__main__':
    unittest.main()

