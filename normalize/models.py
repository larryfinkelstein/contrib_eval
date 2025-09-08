"""
Unified data models for normalized entities and events.
"""

from typing import List, Optional, Dict, Any

class User:
    """
    Normalized user entity.
    """
    def __init__(self, user_id: str, display_name: str, emails: List[str], source_handles: Dict[str, str]):
        self.user_id = user_id
        self.display_name = display_name
        self.emails = emails
        self.source_handles = source_handles  # e.g. {'jira': '...', 'github': '...', 'confluence': '...'}

class Issue:
    """
    Normalized issue entity.
    """
    def __init__(self, issue_id: str, key: str, title: str, type: str, priority: Optional[str] = None, story_points: Optional[float] = None, status_history: Optional[List[str]] = None, assignees: Optional[List[str]] = None, created_at: Optional[str] = None, resolved_at: Optional[str] = None):
        self.issue_id = issue_id
        self.key = key
        self.title = title
        self.type = type  # Story/Bug/Task
        self.priority = priority
        self.story_points = story_points
        self.status_history = status_history or []
        self.assignees = assignees or []
        self.created_at = created_at
        self.resolved_at = resolved_at

class ContributionEvent:
    """
    Unified event schema for contributions.
    """
    def __init__(self, event_id: str, source: str, type: str, timestamp: str, actor_user_id: str, targets: Dict[str, Any], metadata: Dict[str, Any]):
        self.event_id = event_id
        self.source = source  # jira/github/confluence
        self.type = type  # commit, pr_open, pr_merge, pr_review, issue_comment, page_create, page_update, worklog, attachment
        self.timestamp = timestamp
        self.actor_user_id = actor_user_id
        self.targets = targets  # e.g. {'issue_id': [...], 'pr_id': ..., 'repo': ..., 'page_id': ...}
        self.metadata = metadata  # e.g. {'loc_added': ..., 'files_changed': ..., 'review_decision': ..., 'time_spent': ..., 'reaction_count': ...}

class PR:
    """
    Normalized pull request entity.
    """
    def __init__(self, pr_id: str, repo: str, title: str, state: str, created_at: str, merged_at: Optional[str], additions: int, deletions: int, changed_files: int, review_count: int, comments_count: int, linked_issue_ids: Optional[List[str]] = None):
        self.pr_id = pr_id
        self.repo = repo
        self.title = title
        self.state = state
        self.created_at = created_at
        self.merged_at = merged_at
        self.additions = additions
        self.deletions = deletions
        self.changed_files = changed_files
        self.review_count = review_count
        self.comments_count = comments_count
        self.linked_issue_ids = linked_issue_ids or []

class BugLink:
    """
    Links bugs to their origin issues with evidence.
    """
    def __init__(self, bug_issue_id: str, origin_issue_id: str, evidence: str):
        self.bug_issue_id = bug_issue_id
        self.origin_issue_id = origin_issue_id
        self.evidence = evidence  # text match, link type, PR hash proximity
