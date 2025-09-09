from correlate.models import EvaluationResult
from report import renderer


def test_render_html_with_jinja_users():
    # ensure Jinja2 is present in the venv for templated rendering
    users = [
        {
            'user_id': 'u1',
            'display_name': 'Alice Jinja',
            'evaluation': EvaluationResult(involvement=2, significance=3.5, effectiveness=0.8, complexity=1.0, time_required=4.0, bugs_and_fixes=0),
            'links': [],
        }
    ]
    html = renderer.render(result=None, fmt='html', users=users, summary={'score': 10}, generated_at='now', scope='s')
    assert isinstance(html, str)
    assert 'Alice Jinja' in html
    assert 'Involvement' in html or 'Contribution' in html
