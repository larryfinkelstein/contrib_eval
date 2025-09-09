"""
Report renderer: generate simple HTML/Markdown/CSV summaries from EvaluationResult.
Supports optional Jinja2-based HTML rendering using report/templates/report.html.j2 when available.
"""

from typing import Optional, List, Dict, Any
from correlate.models import EvaluationResult
import os
import importlib.util
import json
import io
import csv


def render_text(result: EvaluationResult) -> str:
    """Render a simple plain-text summary."""
    return str(result)


def render_markdown(result: EvaluationResult) -> str:
    """Render a Markdown section for a single user's evaluation."""
    md = []
    md.append("# Contribution Summary\n")
    md.append(f"- Involvement: **{result.involvement}**")
    md.append(f"- Significance: **{result.significance:.2f}**")
    md.append(f"- Effectiveness: **{result.effectiveness:.2f}**")
    md.append(f"- Complexity: **{result.complexity:.2f}**")
    md.append(f"- Time Required: **{result.time_required:.2f} hours**")
    md.append(f"- Bugs and Fixes: **{result.bugs_and_fixes}**")
    return "\n".join(md)


def render_csv(result: EvaluationResult) -> str:
    """Render a single-line CSV summary with a header."""
    header = "involvement,significance,effectiveness,complexity,time_required,bugs_and_fixes"
    row = f"{result.involvement},{result.significance},{result.effectiveness},{result.complexity},{result.time_required},{result.bugs_and_fixes}"
    return header + "\n" + row


def _append_evaluation_html(html_list: List[str], ev: Optional[EvaluationResult], full: bool = False):
    """Module-level helper to append evaluation fields to an HTML list."""
    if not ev:
        return
    html_list.append(f"<p>Involvement: {ev.involvement}</p>")
    html_list.append(f"<p>Significance: {ev.significance:.2f}</p>")
    if full:
        html_list.append(f"<p>Effectiveness: {ev.effectiveness:.2f}</p>")
        html_list.append(f"<p>Complexity: {ev.complexity:.2f}</p>")
        html_list.append(f"<p>Time Required: {ev.time_required:.2f} hours</p>")
        html_list.append(f"<p>Bugs and Fixes: {ev.bugs_and_fixes}</p>")


def _get_user_name(u: Any) -> str:
    """Return a display name for a user entry which may be a dict or a string-like object."""
    if isinstance(u, dict):
        return u.get('display_name') or u.get('user_id') or ''
    return str(u)


def render_html_fallback(evaluation: Optional[EvaluationResult] = None, users: Optional[List[Dict[str, Any]]] = None, metrics: Optional[dict] = None) -> str:
    """Simple HTML fallback renderer that supports either single evaluation or users list."""
    html = ["<html><body>"]

    if users:
        html.append("<h1>Contribution Report</h1>")
        for u in users:
            ev = u.get('evaluation') if isinstance(u, dict) else None
            name = _get_user_name(u)
            html.append(f"<h2>{name}</h2>")
            _append_evaluation_html(html, ev, full=False)
    elif evaluation:
        html.append("<h1>Contribution Summary</h1>")
        _append_evaluation_html(html, evaluation, full=True)
    else:
        html.append("<h1>Contribution Report</h1>")
        html.append("<p>No evaluation data available.</p>")

    if metrics:
        html.append("<h3>Metrics</h3>")
        html.append("<pre>" + str(metrics) + "</pre>")

    html.append("</body></html>")
    return "\n".join(html)


def _render_users_markdown_with_jinja(users: List[Dict[str, Any]]) -> str:
    """Render per-user markdown using the section_user.md.j2 template when Jinja2 is available.

    Returns rendered markdown string or raises on template errors.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    tmpl_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(tmpl_dir), autoescape=select_autoescape(['html', 'xml']))
    tmpl = env.get_template('section_user.md.j2')
    parts = []
    for u in users:
        ev = u.get('evaluation') if isinstance(u, dict) else None
        parts.append(tmpl.render(user=u, evaluation=ev, links=u.get('links', []) if isinstance(u, dict) else []))
    return '\n\n---\n\n'.join(parts)


def _render_users_markdown_fallback(users: List[Dict[str, Any]]) -> str:
    """Simple fallback for per-user markdown rendering without Jinja2."""
    parts = []
    for u in users:
        ev = u.get('evaluation') if isinstance(u, dict) else None
        name = _get_user_name(u)
        if ev:
            parts.append(f"## {name}\n\n" + render_markdown(ev))
        else:
            parts.append(f"## {name}\n\n_No evaluation available._")
    return "\n\n".join(parts)


def _extract_eval_fields(ev: Any):
    """Return normalized tuple of evaluation fields (involvement, significance, effectiveness, complexity, time_required, bugs).

    Supports ev being either a plain dict or an EvaluationResult-like object. Missing values are returned as empty strings.
    """
    if not ev:
        return ('', '', '', '', '', '')
    if isinstance(ev, dict):
        return (
            ev.get('involvement', ''),
            ev.get('significance', ''),
            ev.get('effectiveness', ''),
            ev.get('complexity', ''),
            ev.get('time_required', ''),
            ev.get('bugs_and_fixes', ''),
        )
    # assume object with attributes
    return (
        getattr(ev, 'involvement', ''),
        getattr(ev, 'significance', ''),
        getattr(ev, 'effectiveness', ''),
        getattr(ev, 'complexity', ''),
        getattr(ev, 'time_required', ''),
        getattr(ev, 'bugs_and_fixes', ''),
    )


def _format_user_csv_row(u: Any) -> list:
    """Return a CSV row for a user entry (supports dicts with evaluation dicts or EvaluationResult objects)."""
    ev = u.get('evaluation') if isinstance(u, dict) else None
    inv, sig, eff, comp, time_req, bugs = _extract_eval_fields(ev)

    return [
        u.get('user_id') if isinstance(u, dict) else _get_user_name(u),
        u.get('display_name') if isinstance(u, dict) else '',
        inv,
        sig,
        eff,
        comp,
        time_req,
        bugs,
    ]


def _render_csv_choice(result: Optional[EvaluationResult], users: Optional[List[Dict[str, Any]]] = None) -> str:
    """Render CSV for either a single EvaluationResult or a list of users."""
    if users:
        output = io.StringIO()
        writer = csv.writer(output)
        header = ['user_id', 'display_name', 'involvement', 'significance', 'effectiveness', 'complexity', 'time_required', 'bugs_and_fixes']
        writer.writerow(header)
        for u in users:
            row = _format_user_csv_row(u)
            writer.writerow(row)
        return output.getvalue()
    if result:
        return render_csv(result)
    return ''


def _render_markdown_choice(result: Optional[EvaluationResult], users: Optional[List[Dict[str, Any]]]) -> str:
    """Choose the appropriate evaluation to render as markdown.

    If a users list is provided, attempt to use the Jinja2 per-user template; otherwise fall back to simple concatenation.
    """
    if users:
        if importlib.util.find_spec('jinja2') is not None:
            try:
                return _render_users_markdown_with_jinja(users)
            except Exception:
                # fall back to simple concatenation
                return _render_users_markdown_fallback(users)
        return _render_users_markdown_fallback(users)

    if result is None:
        return ''
    return render_markdown(result)


def render_json(users: Optional[List[Dict[str, Any]]]) -> str:
    """Export the users list (including their evaluation fields) as JSON."""
    if not users:
        return '[]'
    serializable = []
    for u in users:
        if isinstance(u, dict):
            ev = u.get('evaluation')
            ev_obj = None
            if ev:
                # support both EvaluationResult objects and plain dicts
                if isinstance(ev, dict):
                    ev_obj = {
                        'involvement': ev.get('involvement'),
                        'significance': ev.get('significance'),
                        'effectiveness': ev.get('effectiveness'),
                        'complexity': ev.get('complexity'),
                        'time_required': ev.get('time_required'),
                        'bugs_and_fixes': ev.get('bugs_and_fixes'),
                    }
                else:
                    ev_obj = {
                        'involvement': getattr(ev, 'involvement', None),
                        'significance': getattr(ev, 'significance', None),
                        'effectiveness': getattr(ev, 'effectiveness', None),
                        'complexity': getattr(ev, 'complexity', None),
                        'time_required': getattr(ev, 'time_required', None),
                        'bugs_and_fixes': getattr(ev, 'bugs_and_fixes', None),
                    }
            su = dict(u)
            su['evaluation'] = ev_obj
            serializable.append(su)
        else:
            serializable.append({'user': str(u)})
    return json.dumps(serializable, indent=2)


def _render_html_choice(
    result: Optional[EvaluationResult],
    users: Optional[List[Dict[str, Any]]],
    metrics: Optional[dict],
    summary: Optional[dict],
    generated_at: Optional[str],
    scope: Optional[str],
) -> str:
    """Attempt Jinja2 rendering when available, otherwise fall back to simple HTML renderer."""
    if importlib.util.find_spec('jinja2') is not None:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        tmpl_dir = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(tmpl_dir), autoescape=select_autoescape(['html', 'xml']))
        tmpl = env.get_template('report.html.j2')
        context = {
            'evaluation': result,
            'metrics': metrics or {},
            'users': users,
            'summary': summary,
            'generated_at': generated_at,
            'scope': scope,
        }
        return tmpl.render(**context)
    return render_html_fallback(evaluation=result, users=users, metrics=metrics)


def render(
    result: Optional[EvaluationResult] = None,
    fmt: str = 'text',
    metrics: Optional[dict] = None,
    users: Optional[List[Dict[str, Any]]] = None,
    summary: Optional[dict] = None,
    generated_at: Optional[str] = None,
    scope: Optional[str] = None,
) -> str:
    """Main render function.

    Backwards-compatible: previously callers passed a single EvaluationResult as the first arg and metrics via metrics.
    New callers can supply users (list of user dicts), summary (overall), generated_at and scope for the Jinja template.
    """
    fmt_l = (fmt or 'text').lower()
    if fmt_l in ('md', 'markdown'):
        return _render_markdown_choice(result, users)
    if fmt_l == 'csv':
        return _render_csv_choice(result, users)
    if fmt_l in ('html', 'htm'):
        return _render_html_choice(result, users, metrics, summary, generated_at, scope)
    if fmt_l in ('json', 'js'):
        return render_json(users)
    return render_text(result) if result else ''


def render_html(
    result: Optional[EvaluationResult] = None,
    metrics: Optional[dict] = None,
    users: Optional[List[Dict[str, Any]]] = None,
    summary: Optional[dict] = None,
    generated_at: Optional[str] = None,
    scope: Optional[str] = None,
) -> str:
    """Convenience wrapper to render HTML using the main render() function.

    Exposed for backward compatibility with tests and external callers that import
    a dedicated render_html function.
    """
    return render(result, fmt='html', metrics=metrics, users=users, summary=summary, generated_at=generated_at, scope=scope)
