import json
import webbrowser
from pathlib import Path
from cli import _write_report_file, _render_users_report


def test_write_report_file_creates_file(tmp_path, monkeypatch):
    base = str(tmp_path / 'out_report')
    content = 'hello world'
    _write_report_file(base, 'txt', content, open_html=False)
    p = Path(f"{base}.txt")
    assert p.exists()
    assert p.read_text(encoding='utf-8') == content


def test_write_report_file_opens_html(monkeypatch, tmp_path):
    # monkeypatch webbrowser.open to capture calls and avoid launching a real browser
    called = {}

    def fake_open(url):
        called['url'] = url
        return True

    monkeypatch.setattr(webbrowser, 'open', fake_open)

    base = str(tmp_path / 'out_report2')
    html = '<html><body>ok</body></html>'
    _write_report_file(base, 'html', html, open_html=True)
    p = Path(f"{base}.html")
    assert p.exists()
    assert '<html' in p.read_text(encoding='utf-8')
    # ensure webbrowser.open was invoked via the helper
    assert 'url' in called


def test_render_users_report_json(tmp_path):
    users = [
        {
            'user_id': 'u1',
            'display_name': 'Helper Test',
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
    out = _render_users_report('json', users, None, '2025-01-01', '2025-01-31')
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert parsed[0]['display_name'] == 'Helper Test'
