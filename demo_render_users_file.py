"""
Demo: read a JSON users file (with per-user evaluation dicts) and render a combined multi-user HTML report.
Writes demo_report_users_file.html in the repo root.
"""

import json
from datetime import datetime, timezone
from report.renderer import render
from pathlib import Path

sample_path = Path('demo_users.json')
if not sample_path.exists():
    sample = [
        {
            'user_id': 'u1',
            'display_name': 'Alice File',
            'evaluation': {
                'involvement': 5,
                'significance': 4.2,
                'effectiveness': 0.9,
                'complexity': 3.1,
                'time_required': 18.5,
                'bugs_and_fixes': 1,
            },
            'links': [{'bug_issue_id': 'PROJ-123', 'origin_issue_id': 'pr-1', 'evidence': 'PR title contains PROJ-123'}],
        },
        {
            'user_id': 'u2',
            'display_name': 'Bob File',
            'evaluation': {
                'involvement': 3,
                'significance': 3.0,
                'effectiveness': 0.67,
                'complexity': 2.0,
                'time_required': 8.0,
                'bugs_and_fixes': 2,
            },
            'links': [],
        },
    ]
    sample_path.write_text(json.dumps(sample, indent=2), encoding='utf-8')
    print(f'Wrote sample users file to {sample_path}')

users = json.loads(sample_path.read_text(encoding='utf-8'))
summary = {
    'metrics': {
        'involvement': sum(u['evaluation']['involvement'] for u in users if u.get('evaluation')),
        'significance': sum(u['evaluation']['significance'] for u in users if u.get('evaluation')) / len(users),
    },
    'score': 100,
}

generated_at = datetime.now(timezone.utc).isoformat()
scope = 'demo'
html = render(result=None, fmt='html', metrics=summary['metrics'], users=users, summary=summary, generated_at=generated_at, scope=scope)
out = 'demo_report_users_file.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Wrote multi-user report to {out} ({len(html)} bytes)')
