# Test to enforce cognitive/cyclomatic complexity thresholds for renderer.py
# This test uses radon when available; if radon is not installed the test is skipped.
import pathlib
import pytest

try:
    from radon.complexity import cc_visit
except Exception:
    pytest.skip("radon not installed - complexity test skipped", allow_module_level=True)


def test_renderer_complexity_threshold():
    """Fail if any function in report/renderer.py exceeds the configured complexity threshold.

    The threshold is intentionally conservative; adjust as needed. If radon is not
    installed in CI, the test will be skipped so it won't block existing pipelines.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    renderer_path = repo_root / 'report' / 'renderer.py'
    assert renderer_path.exists(), f"renderer.py not found at {renderer_path}"

    src = renderer_path.read_text(encoding='utf-8')
    blocks = cc_visit(src)

    # complexity threshold (cyclomatic complexity). Change if you want stricter/looser limits.
    THRESHOLD = 12

    offenders = [(b.name, b.complexity, b.lineno) for b in blocks if b.complexity > THRESHOLD]
    if offenders:
        offenders_str = '\n'.join([f"{name} (complexity={comp}) at line {lineno}" for name, comp, lineno in offenders])
        pytest.fail(f"Complexity threshold exceeded in report/renderer.py (threshold={THRESHOLD}):\n{offenders_str}")

