from report import renderer
from correlate.models import EvaluationResult


def _make_eval():
    return EvaluationResult(1.0, 2.5, 3.5, 4.5, 5.0, 2)


def test_append_evaluation_html_brief():
    html = []
    ev = _make_eval()
    renderer._append_evaluation_html(html, ev, full=False)
    joined = "".join(html)
    assert "Involvement: 1.0" in joined
    assert "Significance: 2.50" in joined
    assert "Effectiveness" not in joined


def test_append_evaluation_html_full():
    html = []
    ev = _make_eval()
    renderer._append_evaluation_html(html, ev, full=True)
    joined = "".join(html)
    assert "Effectiveness: 3.50" in joined
    assert "Complexity: 4.50" in joined
    assert "Time Required: 5.00 hours" in joined


def test_get_user_name_variants():
    assert renderer._get_user_name({"display_name": "Alice", "user_id": "a1"}) == "Alice"
    assert renderer._get_user_name({"user_id": "bob"}) == "bob"
    assert renderer._get_user_name("Charlie") == "Charlie"


def test_render_markdown_choice_with_users():
    ev = _make_eval()
    users = [{"display_name": "U", "evaluation": ev}]
    md = renderer._render_markdown_choice(None, users)
    assert "Involvement" in md and "**1.0**" in md


def test_render_markdown_choice_with_result():
    ev = _make_eval()
    md = renderer._render_markdown_choice(ev, None)
    assert "Involvement" in md


def test_render_csv_choice():
    ev = _make_eval()
    csv = renderer._render_csv_choice(ev)
    assert csv.startswith("involvement,significance")
    assert "1.0" in csv.splitlines()[1]


def test_render_csv_choice_none():
    assert renderer._render_csv_choice(None) == ""


def test_render_html_choice_fallback_for_result(monkeypatch):
    # force fallback path by making jinja2 unavailable
    monkeypatch.setattr('importlib.util.find_spec', lambda name: None)
    ev = _make_eval()
    out = renderer._render_html_choice(ev, None, None, None, None, None)
    assert "<h1>Contribution Summary</h1>" in out
    assert "Involvement: 1.0" in out


def test_render_html_choice_fallback_for_users(monkeypatch):
    monkeypatch.setattr('importlib.util.find_spec', lambda name: None)
    ev = _make_eval()
    users = [{"display_name": "Zed", "evaluation": ev}]
    out = renderer._render_html_choice(None, users, None, None, None, None)
    assert "<h2>Zed</h2>" in out
    assert "Significance: 2.50" in out
