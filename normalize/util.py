"""
Normalization utility helpers.
Small helpers to normalize raw payloads into normalize.models entities.
"""
from typing import Dict, Any
from normalize.models import User, Issue


def normalize_user(raw: Dict[str, Any]) -> User:
    """Create a normalized User from a raw provider dict.
    Expected keys vary by provider; function extracts common fields.
    """
    user_id = raw.get('accountId') or raw.get('id') or raw.get('user_id') or str(raw.get('username') or raw.get('login') or '')
    display_name = raw.get('displayName') or raw.get('name') or raw.get('login') or ''
    emails = []
    if raw.get('emailAddress'):
        emails.append(raw.get('emailAddress'))
    if raw.get('email'):
        emails.append(raw.get('email'))
    source_handles = {}
    if raw.get('key'):
        source_handles['jira'] = raw.get('key')
    if raw.get('login'):
        source_handles['github'] = raw.get('login')
    if raw.get('username'):
        source_handles['confluence'] = raw.get('username')
    return User(user_id=str(user_id), display_name=display_name, emails=emails, source_handles=source_handles)


def _extract_assignees(fields: Dict[str, Any]) -> list:
    """Return a list with a single assignee identifier if present, otherwise an empty list."""
    if not isinstance(fields, dict):
        return []
    assignee = fields.get('assignee') or {}
    identifier = assignee.get('accountId') or assignee.get('name') or assignee.get('displayName')
    return [identifier] if identifier else []


def normalize_issue(raw: Dict[str, Any]) -> Issue:
    """Create a normalized Issue from a raw Jira issue dict.
    This function is intentionally conservative and fills missing fields with None/defaults.
    """
    issue_id = raw.get('id') or raw.get('key') or ''
    key = raw.get('key') or (raw.get('fields') or {}).get('key') or ''
    fields = raw.get('fields') or {}
    title = fields.get('summary') or raw.get('title') or ''
    issue_type = (fields.get('issuetype') or {}).get('name') if isinstance(fields.get('issuetype'), dict) else fields.get('issuetype') or raw.get('type') or 'Task'
    priority = (fields.get('priority') or {}).get('name') if isinstance(fields.get('priority'), dict) else fields.get('priority')
    story_points = fields.get('customfield_10016') or fields.get('storyPoints') if fields else None
    status_history = []
    assignees = _extract_assignees(fields)
    created_at = fields.get('created') or raw.get('created_at') or None
    resolved_at = fields.get('resolutiondate') or raw.get('resolved_at') or None
    return Issue(issue_id=str(issue_id), key=key, title=title, type=issue_type, priority=priority, story_points=story_points, status_history=status_history, assignees=assignees, created_at=created_at, resolved_at=resolved_at)
