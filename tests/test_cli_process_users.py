import json
from argparse import Namespace
from pathlib import Path

from cli import _process_users_file


def test_process_users_file_writes_exports(tmp_path):
    users = [
        {
            'user_id': 'u1',
            'display_name': 'Alice Test',
            'evaluation': {
                'involvement': 4,
                'significance': 3.5,
                'effectiveness': 0.9,
                'complexity': 2.0,
                'time_required': 10.0,
                'bugs_and_fixes': 0,
            },
            'links': [],
        },
        {
            'user_id': 'u2',
            'display_name': 'Bob Test',
            'evaluation': {
                'involvement': 2,
                'significance': 2.0,
                'effectiveness': 0.5,
                'complexity': 1.0,
                'time_required': 3.0,
                'bugs_and_fixes': 1,
            },
            'links': [],
        },
    ]

    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps(users))

    out_base = str(tmp_path / "report_multi")

    args = Namespace(
        users_file=str(users_file),
        summary_file="",
        output="html",
        out_file=out_base,
        export_all=True,
        start="2025-01-01",
        end="2025-01-31",
        open=False,
    )

    wrote = _process_users_file(args)
    assert wrote is True

    expected = ["html", "md", "csv", "json"]
    for ext in expected:
        path = Path(f"{out_base}.{ext}")
        assert path.exists(), f"Expected {path} to exist"
        content = path.read_text(encoding='utf-8')
        assert len(content) > 0
        # basic sanity checks
        if ext == 'html':
            assert '<html' in content.lower()
        if ext == 'json':
            # should be a JSON array
            parsed = json.loads(content)
            assert isinstance(parsed, list)
            assert len(parsed) == 2
