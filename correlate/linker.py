"""
Linker heuristics to associate commits/PRs/comments/pages with Jira issues.
Simple, dependency-free heuristics:
- explicit key match in text
- key in PR/commit titles
- fallback: look for numeric proximity (TODO)
"""
import re
from typing import List, Dict, Optional
from normalize.models import BugLink


def find_issue_keys_in_text(text: str, key_pattern: Optional[str] = r"[A-Z][A-Z0-9]+-\d+") -> List[str]:
    if not text:
        return []
    pattern = re.compile(key_pattern)
    return list({m.group(0) for m in pattern.finditer(text)})


# helper: extract string values from a mapping
def _extract_string_values(mapping: Dict) -> List[str]:
    if not isinstance(mapping, dict):
        return []
    return [v for v in mapping.values() if isinstance(v, str) and v]


# helper: extract textual fields from an event
def collect_text_fields(ev: Dict) -> List[str]:
    # gather core text fields with a single comprehension to reduce branching
    core_vals = (ev.get(k) for k in ("title", "subject", "message", "body"))
    text_fields: List[str] = [v for v in core_vals if isinstance(v, str) and v]

    # collect string values from metadata/meta and targets
    text_fields.extend(_extract_string_values(ev.get("metadata") or ev.get("meta") or {}))
    text_fields.extend(_extract_string_values(ev.get("targets") or {}))

    return text_fields


# helper: derive origin identifier for an event
def derive_origin(ev: Dict) -> str:
    return ev.get("id") or ev.get("event_id") or ev.get("sha") or str(ev.get("timestamp", ""))


# helper: find candidate keys for a set of text fields
def find_candidates(texts: List[str], known_keys: set, key_pattern: str) -> Dict[str, str]:
    found_map: Dict[str, str] = {}
    for txt in texts:
        keys = find_issue_keys_in_text(txt, key_pattern)
        if not keys:
            continue
        excerpt = txt[:100]
        for k in keys:
            if k in known_keys and k not in found_map:
                found_map[k] = f"text match in field: '{excerpt}'"
    return found_map


def event_links(ev: Dict, known_keys: set, key_pattern: str) -> List[BugLink]:
    """Return BugLink objects discovered for a single event (or empty list)."""
    texts = collect_text_fields(ev)
    if not texts:
        return []
    candidates = find_candidates(texts, known_keys, key_pattern)
    if not candidates:
        return []
    origin = derive_origin(ev)
    return [BugLink(bug_issue_id=bid, origin_issue_id=origin, evidence=evidence)
            for bid, evidence in candidates.items()]


def link_events_to_issues(events: List[Dict], issues: List[Dict], key_pattern: Optional[str] = None) -> List[BugLink]:
    """
    Attempt to link a list of raw events (dicts) to issues by scanning text fields for issue keys.

    Parameters:
        events: list of event dicts, each should have textual fields like 'title' or 'body' or 'metadata'.
        issues: list of issue dicts (from Jira) to extract keys from.
        key_pattern: optional regex for issue keys. Defaults to e.g. PROJ-123.

    Returns:
        list of BugLink objects describing discovered links.
    """
    key_pattern = key_pattern or r"[A-Z][A-Z0-9]+-\d+"

    # build set of known issue keys for quick membership test
    known_keys = {iss.get("key") or iss.get("fields", {}).get("key") for iss in issues if (iss.get("key") or iss.get("fields", {}).get("key"))}

    links: List[BugLink] = []
    for ev in events:
        links.extend(event_links(ev, known_keys, key_pattern))
    return links
