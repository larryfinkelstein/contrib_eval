import json
import sys
from pathlib import Path

from cli import main


def test_cli_main_users_file_runs(tmp_path, monkeypatch):
    # write users.json
    users = [
        {
            'user_id': 'u1',
            'display_name': 'CLI Alice',
            'evaluation': {
                'involvement': 1,
                'significance': 2.0,
                'effectiveness': 0.5,
                'complexity': 1.0,
                'time_required': 2.0,
                'bugs_and_fixes': 0,
            },
            'links': [],
        }
    ]
    users_file = tmp_path / 'users.json'
    users_file.write_text(json.dumps(users), encoding='utf-8')

    out_base = str(tmp_path / 'report_cli')

    argv = [
        'cli.py',
        '--start',
        '2025-01-01',
        '--end',
        '2025-01-31',
        '--user',
        'dummy',
        '--jira_project',
        'MCLD',
        '--confluence_space',
        'SMARTINT',
        '--github_org',
        'org',
        '--jira_token',
        't',
        '--confluence_token',
        't',
        '--github_token',
        't',
        '--users-file',
        str(users_file),
        '--export-all',
        '--out-file',
        out_base,
    ]
    monkeypatch.setattr(sys, 'argv', argv)
    # run main; should exit normally after processing users-file
    main()

    for ext in ('html', 'md', 'csv', 'json'):
        p = Path(f"{out_base}.{ext}")
        assert p.exists()
        assert p.read_text(encoding='utf-8')
