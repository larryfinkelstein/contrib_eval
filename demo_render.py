"""
Demo script to render a multi-user HTML report using report.renderer.render
Also writes markdown, csv and json exports for the same users list.
"""

from correlate.models import EvaluationResult
from report.renderer import render
from datetime import datetime, timezone

# Build sample users with EvaluationResult objects and optional links
users = [
    {
        'user_id': 'u1',
        'display_name': 'Alice Example',
        'evaluation': EvaluationResult(involvement=5, significance=4.2, effectiveness=0.9, complexity=3.1, time_required=18.5, bugs_and_fixes=1),
        'links': [
            {'bug_issue_id': 'PROJ-123', 'origin_issue_id': 'pr-1', 'evidence': 'PR title contains PROJ-123'},
        ],
    },
    {
        'user_id': 'u2',
        'display_name': 'Bob Example',
        'evaluation': EvaluationResult(involvement=3, significance=3.0, effectiveness=0.67, complexity=2.0, time_required=8.0, bugs_and_fixes=2),
        'links': [],
    },
]

summary = {
    'metrics': {
        'involvement': 8,
        'significance': 3.6,
        'effectiveness': 0.79,
        'complexity': 2.7,
        'time_required': 26.5,
        'bugs_and_fixes': 3,
        'bug_fallout': 0.375,
    },
    'score': 42.5,
}

generated_at = datetime.now(timezone.utc).isoformat()
scope = '2025-01-01 to 2025-01-31'

# Render HTML (uses Jinja2 template if available)
html = render(result=None, fmt='html', metrics=summary['metrics'], users=users, summary=summary, generated_at=generated_at, scope=scope)
out_path = 'demo_report_multi.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Rendered {out_path} ({len(html)} bytes)')

# Render combined Markdown
md = render(result=None, fmt='md', users=users)
md_path = 'demo_report_multi.md'
with open(md_path, 'w', encoding='utf-8') as f:
    f.write(md)
print(f'Wrote markdown {md_path} ({len(md)} bytes)')

# Render CSV (users list)
csv_out = render(result=None, fmt='csv', users=users)
csv_path = 'demo_report_multi.csv'
with open(csv_path, 'w', encoding='utf-8', newline='') as f:
    f.write(csv_out)
print(f'Wrote CSV {csv_path} ({len(csv_out)} bytes)')

# Render JSON
json_out = render(result=None, fmt='json', users=users)
json_path = 'demo_report_multi.json'
with open(json_path, 'w', encoding='utf-8') as f:
    f.write(json_out)
print(f'Wrote JSON {json_path} ({len(json_out)} bytes)')
