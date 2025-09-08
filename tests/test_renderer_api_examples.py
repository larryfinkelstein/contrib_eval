from normalize.models import ContributionEvent
from scoring.metrics import compute_metrics
from report.renderer import render_markdown, render_csv, render_html


def _make_simple_events():
    # Create a couple of minimal ContributionEvent objects used by compute_metrics
    e1 = ContributionEvent('e1', 'github', 'commit', '2025-01-01T00:00:00Z', 'user1', {'repo': 'r'}, {'description': 'Initial commit', 'complexity': 3, 'time_spent': 1.0, 'bugs_reported': 0})
    e2 = ContributionEvent('e2', 'jira', 'Bug', '2025-01-02T00:00:00Z', 'user1', {'issue_id': ['ISSUE-1']}, {'description': 'Fix bug', 'complexity': 2, 'time_spent': 2.0, 'bugs_reported': 1})
    return [e1, e2]


def test_render_helpers_from_compute_metrics():
    events = _make_simple_events()
    res = compute_metrics(events)
    evaluation = res.get('evaluation_result')
    metrics = res.get('metrics')

    # render_markdown should include a header
    md = render_markdown(evaluation)
    assert isinstance(md, str)
    assert 'Contribution Summary' in md

    # render_csv should include header columns
    csv = render_csv(evaluation)
    assert isinstance(csv, str)
    assert 'involvement,significance' in csv

    # render_html should produce HTML string (fallback or template)
    html = render_html(result=evaluation, metrics=metrics)
    assert isinstance(html, str)
    assert ('<h1' in html) or ('Contribution Summary' in html)
