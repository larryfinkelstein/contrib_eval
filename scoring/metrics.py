"""
Scoring metrics conversion utilities.
Converts raw Jira/Confluence/GitHub payloads into normalized ContributionEvent objects.
"""
from typing import List, Dict, Any
from normalize.models import ContributionEvent
from correlate.models import EvaluationResult
from .utils import load_weights, compute_weighted_score
from .utils import compute_user_time_factors, apply_smoothing, DEFAULT_SMOOTHING_ALPHA
import os


def _map_issue_type_to_complexity(issue_type: str) -> int:
    """Map a Jira issue type name to a numeric complexity value."""
    it = (issue_type or '').lower()
    if it == 'bug':
        return 2
    if it == 'story':
        return 5
    return 3


def _get_assignee_actor(fields: Dict[str, Any]) -> str:
    """Return the assignee account id (or empty string) from issue fields."""
    if not isinstance(fields, dict):
        return ''
    assignee = fields.get('assignee') or {}
    return assignee.get('accountId') or ''


def _extract_status_history_from_issue(issue: Dict[str, Any]) -> List[str]:
    """Safely extract a list of status values from an issue changelog."""
    status_history: List[str] = []
    try:
        changelog = issue.get('changelog') or {}
        histories = changelog.get('histories', []) if isinstance(changelog, dict) else []
        for h in histories:
            for it in (h.get('items') or []):
                if (it.get('field') or '').lower() == 'status':
                    status_history.append(it.get('toString') or it.get('to') or '')
    except Exception:
        # return what we've collected so far (or empty list) on any unexpected structure
        return []
    return status_history


def _jira_event_from_issue(issue: Dict[str, Any]) -> ContributionEvent:
    fields = issue.get('fields', {}) if isinstance(issue, dict) else {}
    issue_type = (fields.get('issuetype') or {}).get('name', 'Issue') if fields else 'Issue'
    summary = fields.get('summary', '')
    created = fields.get('created', '')
    event_id = issue.get('id') or issue.get('key') or summary
    actor = _get_assignee_actor(fields)

    complexity = _map_issue_type_to_complexity(issue_type)

    timespent = fields.get('timespent') or 0
    time_spent_hours = float(timespent) / 3600.0 if timespent else 0.0
    bugs_reported = 1 if (issue_type or '').lower() == 'bug' else 0

    status_history = _extract_status_history_from_issue(issue)

    targets = {'issue_id': [issue.get('id') or issue.get('key')]}
    metadata = {
        'description': summary,
        'complexity': complexity,
        'time_spent': time_spent_hours,
        'bugs_reported': bugs_reported,
        'status_history': status_history,
    }
    return ContributionEvent(str(event_id), 'jira', issue_type, created, actor or '', targets, metadata)


def convert_jira_issues_to_events(issues: List[Dict[str, Any]]) -> List[ContributionEvent]:
    events: List[ContributionEvent] = []
    for issue in issues or []:
        events.append(_jira_event_from_issue(issue))
    return events


def convert_confluence_pages_to_events(pages: List[Dict[str, Any]]) -> List[ContributionEvent]:
    events: List[ContributionEvent] = []
    for page in pages or []:
        title = page.get('title') if isinstance(page, dict) else ''
        history = page.get('history', {}) if isinstance(page, dict) else {}
        created = history.get('createdDate') or (page.get('version') or {}).get('when') or ''
        event_id = page.get('id') or title
        actor = (history.get('createdBy') or {}).get('accountId') or (history.get('createdBy') or {}).get('username') or ''
        targets = {'page_id': page.get('id')}
        metadata = {
            'description': title,
            'complexity': 2,
            'time_spent': 0.5,
            'bugs_reported': 0
        }
        events.append(ContributionEvent(str(event_id), 'confluence', 'page_create', created, actor or '', targets, metadata))
    return events


def _github_event_from_item(item: Dict[str, Any]) -> ContributionEvent:
    event_id = item.get('id') or item.get('sha') or item.get('title')
    created = item.get('created_at') or item.get('date') or ''
    actor = (item.get('user') or {}).get('id') or (item.get('author') or {}).get('id') or ''
    title = item.get('title') or item.get('message') or ''
    is_pr = _is_github_pr(item)
    event_type = 'pr_open' if is_pr else 'commit'
    complexity = item.get('complexity', 3)
    time_spent = item.get('time_spent', 0.0)
    bugs_reported = 1 if 'bug' in title.lower() else 0
    targets = _build_github_targets(item)
    metadata = {
        'description': title,
        'complexity': complexity,
        'time_spent': time_spent,
        'bugs_reported': bugs_reported,
        'is_pr': is_pr
    }
    return ContributionEvent(str(event_id), 'github', event_type, created, actor or '', targets, metadata)


def convert_github_items_to_events(items: List[Dict[str, Any]]) -> List[ContributionEvent]:
    events: List[ContributionEvent] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        events.append(_github_event_from_item(item))
    return events


def _is_github_pr(item: Dict[str, Any]) -> bool:
    return bool(item.get('pull_request') or item.get('pull_request_url') or (item.get('html_url') and '/pull/' in str(item.get('html_url'))))


def _build_github_targets(item: Dict[str, Any]) -> Dict[str, Any]:
    pr_part = None
    pr = item.get('pull_request')
    if pr and isinstance(pr, dict):
        pr_part = pr.get('id')
    pr_part = pr_part or item.get('number') or None
    repo = (item.get('repository') or {}).get('name') if isinstance(item.get('repository'), dict) else item.get('repo')
    return {'pr_id': pr_part, 'repo': repo}


def compute_metrics(events: List[ContributionEvent]) -> dict:
    """
    Compute evaluation metrics from a list of normalized ContributionEvent objects.
    Returns a dict with granular metrics, weighted score, and an EvaluationResult instance.
    """
    # basic aggregates
    involvement = len(events)
    if involvement == 0:
        eval_result = EvaluationResult(0,0,0,0,0,0)
        weights = load_weights()
        return {'metrics': {}, 'score': 0.0, 'weights': weights, 'evaluation_result': eval_result}

    sig_total, eff_success, complexity_total, per_user_time, bugs_and_fixes, status_flips_total = _accumulate_event_metrics(events)

    # compute bug_fallout: fraction of events associated with bugs (bugs per contribution)
    bug_fallout = bugs_and_fixes / involvement

    significance = sig_total / involvement
    effectiveness = eff_success / involvement
    complexity = complexity_total / involvement

    # apply per-user time normalization factors
    time_factors = compute_user_time_factors(events)
    adjusted_time_required = 0.0
    for u, t in per_user_time.items():
        f = time_factors.get(u, 1.0)
        adjusted_time_required += t * f

    # instability adjustment: penalize effectiveness for lots of status flips
    avg_flips = (status_flips_total / involvement) if involvement else 0.0
    # reduce effectiveness by up to 50% for very unstable workflows
    instability_factor = max(0.5, 1.0 - (avg_flips * 0.1))
    effectiveness = effectiveness * instability_factor

    metrics = {
        'involvement': involvement,
        'significance': significance,
        'effectiveness': effectiveness,
        'complexity': complexity,
        'time_required': adjusted_time_required,
        'bugs_and_fixes': bugs_and_fixes,
        'bug_fallout': bug_fallout,
        'time_factors': time_factors,
        'status_instability_avg_flips': avg_flips,
    }

    weights = load_weights()
    # apply optional smoothing to metrics before computing score
    alpha_env = os.getenv('CONTRIB_SMOOTHING_ALPHA')
    try:
        alpha = float(alpha_env) if alpha_env is not None else DEFAULT_SMOOTHING_ALPHA
    except Exception:
        alpha = DEFAULT_SMOOTHING_ALPHA

    if alpha < 1.0:
        smoothed_metrics = apply_smoothing(metrics, alpha=alpha)
    else:
        smoothed_metrics = metrics

    score = compute_weighted_score(smoothed_metrics, weights)

    eval_result = EvaluationResult(
        involvement=involvement,
        significance=significance,
        effectiveness=effectiveness,
        complexity=complexity,
        time_required=adjusted_time_required,
        bugs_and_fixes=bugs_and_fixes,
    )

    return {
        'metrics': metrics,
        'smoothed_metrics': smoothed_metrics,
        'score': score,
        'weights': weights,
        'evaluation_result': eval_result,
    }


def _significance_for_event(e: ContributionEvent, meta: Dict[str, Any]) -> int:
    etype = getattr(e, 'type', '')
    if etype == 'pr_merge' or meta.get('review_decision') == 'merged':
        return 6
    if etype in ('pr_open', 'pr_review') or meta.get('is_pr'):
        return 5
    if etype in ('Story',):
        return 4
    return 2


def _accumulate_event_metrics(events: List[ContributionEvent]):
    sig_total = 0.0
    eff_success = 0
    complexity_total = 0.0
    per_user_time: Dict[str, float] = {}
    bugs_and_fixes = 0
    status_flips_total = 0
    for e in events:
        meta = getattr(e, 'metadata', {}) or {}
        sig = _significance_for_event(e, meta)
        sig_total += sig
        bugs = int(meta.get('bugs_reported', 0) or 0)
        if bugs == 0:
            eff_success += 1
        complexity_total += float(meta.get('complexity', 0) or 0)
        t_spent = float(meta.get('time_spent', 0.0) or 0.0)
        uid = getattr(e, 'actor_user_id', '') or ''
        per_user_time[uid] = per_user_time.get(uid, 0.0) + t_spent
        bugs_and_fixes += bugs
        sh = meta.get('status_history') or []
        flips = max(0, len(sh) - 1)
        status_flips_total += flips
    return sig_total, eff_success, complexity_total, per_user_time, bugs_and_fixes, status_flips_total

