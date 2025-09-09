"""
CLI entry point for contrib_eval. Wires the pipeline: ingest -> normalize -> score -> report
"""

import argparse
import webbrowser
import os
from datetime import datetime, timezone
from ingest.jira import JiraClient
from ingest.confluence import ConfluenceClient
from ingest.github import GitHubClient
from scoring.metrics import (
    convert_jira_issues_to_events,
    convert_confluence_pages_to_events,
    convert_github_items_to_events,
    compute_metrics,
)
from report.renderer import render
from storage.cache import Cache
from storage.cache import configure_retry
import json


def _print_json(obj):
    try:
        import json

        print(json.dumps(obj, indent=2, default=str))
    except Exception:
        print(obj)


def _print_cache_stats(cache: Cache):
    stats = cache.stats()
    _print_json(stats)


def _print_cache_list(cache: Cache):
    items = cache.list_keys(limit=1000)
    _print_json(items)


def _print_cache_get(cache: Cache, key: str):
    entry = cache.get(key)
    if entry is None:
        print(f"Cache key not found: {key}")
    else:
        _print_json(entry)


def _remove_cache_key(cache: Cache, key: str, force: bool):
    if not force:
        confirm = input(f"Are you sure you want to remove cache key '{key}' from {cache.path}? [y/N]: ")
        if confirm.strip().lower() not in ("y", "yes"):
            print("Aborted cache key removal.")
            return
    removed = cache.delete_key(key)
    if removed:
        print(f"Removed {removed} row(s) for key: {key}")
    else:
        print(f"Cache key not found: {key}")


def _clear_cache(cache: Cache, force: bool):
    if not force:
        confirm = input(f"Are you sure you want to clear the cache at {cache.path}? This cannot be undone. [y/N]: ")
        if confirm.strip().lower() not in ("y", "yes"):
            print("Aborted cache clear.")
            return
    cache.clear()
    print(f"Cleared cache at {cache.path}")


def _handle_cache_actions(args) -> Cache | None:
    """Process cache inspection/management flags and return a Cache or None.
    If an inspection/management action is performed, this function prints output and returns None to signal exit.
    """
    # if no cache-only flags, return a live Cache or None for normal pipeline
    if not (args.cache_info or args.cache_clear or args.cache_list or args.cache_get or args.cache_remove):
        return Cache(args.cache) if args.cache else None

    cache_path = args.cache or "cache.db"
    cache = Cache(cache_path)
    try:
        # map flag name to handler callable
        flag_actions = [
            (args.cache_info, lambda: _print_cache_stats(cache)),
            (args.cache_clear, lambda: _clear_cache(cache, args.force)),
            (args.cache_list, lambda: _print_cache_list(cache)),
            (bool(args.cache_get), lambda: _print_cache_get(cache, args.cache_get)),
            (bool(args.cache_remove), lambda: _remove_cache_key(cache, args.cache_remove, args.force)),
        ]
        for enabled, handler in flag_actions:
            if enabled:
                handler()
                return None
        return None
    finally:
        cache.close()


def run_pipeline(args, cache):
    """Execute ingest -> normalize -> score -> render and return (fmt, rendered)."""
    jira = JiraClient(args.jira_token, args.jira_project, cache=cache)
    confluence = ConfluenceClient(args.confluence_token, args.confluence_space, cache=cache)
    github = GitHubClient(args.github_token, args.github_org)

    jira_raw = jira.get_user_issues(args.user, args.start, args.end)
    confluence_raw = confluence.get_user_pages(args.start, args.end)
    github_raw = github.get_user_contributions(args.user, args.start, args.end)

    jira_events = convert_jira_issues_to_events(jira_raw)
    conf_events = convert_confluence_pages_to_events(confluence_raw)
    gh_events = convert_github_items_to_events(github_raw)

    all_events = jira_events + conf_events + gh_events

    metrics_res = compute_metrics(all_events)
    fmt = (args.output or "html").lower()
    rendered = render(metrics_res["evaluation_result"], fmt=fmt, metrics=metrics_res.get("metrics"))
    return fmt, rendered


def _open_file_in_browser(path: str):
    """Open a file URL in the system default web browser."""
    webbrowser.open("file://" + os.path.abspath(path))


def write_output(fmt: str, rendered: str, args):
    """Write output to file or stdout and optionally open HTML in browser."""
    if fmt in ("html", "md", "csv"):
        # choose extension via mapping to avoid nested conditionals
        ext_map = {"html": "html", "md": "md", "csv": "csv"}
        ext = ext_map.get(fmt, "html")
        out_path = args.out_file.strip() or f"contrib_report_{args.user}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.{ext}"
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        print(f"Wrote report to {out_path}")
        if args.open and fmt == "html":
            try:
                _open_file_in_browser(out_path)
            except Exception:
                print("Failed to open browser automatically; file saved at", out_path)
    else:
        print(rendered)


def _resolve_tokens(args, parser):
    """Resolve tokens from CLI args or environment variables and attach them to args.
    Calls parser.error() if any required token is missing.
    """
    jira_token_val = args.jira_token if args.jira_token else os.getenv('JIRA_TOKEN')
    confluence_token_val = args.confluence_token if args.confluence_token else os.getenv('CONFLUENCE_TOKEN')
    github_token_val = args.github_token if args.github_token else os.getenv('GITHUB_TOKEN')

    missing = []
    if not jira_token_val:
        missing.append('jira_token (CLI flag --jira_token or env JIRA_TOKEN)')
    if not confluence_token_val:
        missing.append('confluence_token (CLI flag --confluence_token or env CONFLUENCE_TOKEN)')
    if not github_token_val:
        missing.append('github_token (CLI flag --github_token or env GITHUB_TOKEN)')
    if missing:
        parser.error('Missing required tokens: ' + ', '.join(missing))

    # set resolved token values back onto args for downstream consumers
    args.jira_token = jira_token_val
    args.confluence_token = confluence_token_val
    args.github_token = github_token_val


def _load_json_file(path: str, description: str):
    """Attempt to load a JSON file and return the parsed object or None on failure.
    Errors are printed by the caller; this helper just returns None on failure.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to read {description} {path}: {e}")
        return None


def _render_users_report(fmt_name: str, users, summary, start: str, end: str) -> str:
    """Render the users list for the given format using a common context.

    Extracted to reduce cognitive complexity in _maybe_render_multi_user.
    """
    return render(
        result=None,
        fmt=fmt_name,
        metrics=(summary.get('metrics') if summary else None),
        users=users,
        summary=summary,
        generated_at=datetime.now(timezone.utc).isoformat(),
        scope=f"{start} to {end}",
    )


def _write_report_file(path_base: str, ext: str, content: str, open_html: bool = False):
    """Write the rendered content to a file and optionally open HTML in the browser.

    Extracted to reduce cognitive complexity in _maybe_render_multi_user.
    """
    out_path = path_base if path_base.lower().endswith(f".{ext}") else f"{path_base}.{ext}"
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    # newline='' is safe for CSV on Windows and harmless for other formats
    with open(out_path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(content)
    print(f"Wrote report to {out_path}")
    if open_html:
        try:
            _open_file_in_browser(out_path)
        except Exception:
            print('Failed to open browser automatically; file saved at', out_path)


def _process_users_file(args) -> bool:
    """Load users and optional summary, render and write reports per args.

    Returns True if any output file was written, False otherwise.
    """
    users = _load_json_file(args.users_file, 'users file')
    if users is None:
        return False

    summary = _load_json_file(args.summary_file, 'summary file') if args.summary_file else None
    if args.summary_file and summary is None:
        return False

    fmt = (args.output or 'html').lower()

    export_all = bool(getattr(args, 'export_all', False))
    formats = ('html', 'md', 'csv', 'json') if export_all else (fmt,)

    base = args.out_file.strip() or f"contrib_report_multi_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}" if export_all else None

    wrote_any = False
    for ffmt in formats:
        content = _render_users_report(ffmt, users, summary, args.start, args.end)
        if export_all:
            _write_report_file(base, ffmt, content, open_html=(ffmt == 'html' and args.open))
            wrote_any = True
        else:
            # single-format: delegate to existing write_output for consistency
            write_output(fmt, content, args)
            wrote_any = True
            break

    return wrote_any


def _aggregate_users_from_file(args, cache) -> bool:
    """Load user IDs from the specified file, aggregate evaluations for each user,
    and render a multi-user report.
    """
    user_ids = _load_json_file(args.user_list_file, 'user list file')
    if user_ids is None or not isinstance(user_ids, list):
        print(f"Invalid user list file {args.user_list_file}; expected an array of user IDs.")
        return False

    # instantiate clients once and reuse for all users
    jira = JiraClient(args.jira_token, args.jira_project, cache=cache)
    confluence = ConfluenceClient(args.confluence_token, args.confluence_space, cache=cache)
    github = GitHubClient(args.github_token, args.github_org)

    aggregated_events = []
    for uid in user_ids:
        try:
            jira_raw = jira.get_user_issues(uid, args.start, args.end)
            conf_raw = (
                confluence.get_user_pages(args.start, args.end, user=uid)
                if hasattr(confluence, 'get_user_pages')
                else confluence.get_user_pages(args.start, args.end)
            )
            gh_raw = github.get_user_contributions(uid, args.start, args.end)

            jira_events = convert_jira_issues_to_events(jira_raw)
            conf_events = convert_confluence_pages_to_events(conf_raw)
            gh_events = convert_github_items_to_events(gh_raw)

            aggregated_events.extend(jira_events)
            aggregated_events.extend(conf_events)
            aggregated_events.extend(gh_events)
        except Exception as exc:
            print(f"Warning: failed to fetch events for user {uid}: {exc}")

    if not aggregated_events:
        print("No events aggregated for provided users.")
        return False

    metrics_res = compute_metrics(aggregated_events)
    summary = {'metrics': metrics_res.get('metrics'), 'score': metrics_res.get('score')}
    generated_at = datetime.now(timezone.utc).isoformat()
    scope = f"{args.start} to {args.end}"

    # produce multi-user report using renderer template when available
    rendered = render(
        result=None, fmt='html', metrics=summary['metrics'], users=[{'user_id': u} for u in user_ids], summary=summary, generated_at=generated_at, scope=scope
    )
    out_path = args.out_file.strip() or f"contrib_report_aggregated_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.html"
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(rendered)
    print(f"Wrote aggregated report to {out_path}")
    if args.open:
        try:
            _open_file_in_browser(out_path)
        except Exception:
            pass
    return True


def _maybe_render_multi_user(args) -> bool:
    """If users-file provided, process it and return True to exit early; otherwise return False.

    This wrapper delegates to _process_users_file to keep complexity low while preserving
    existing CLI behavior (always exit early when users-file is provided).
    """
    if not args.users_file:
        return False
    # process users file (result is informational only); always return True to signal the CLI
    # should exit early when a users-file was provided (preserves prior behavior)
    _process_users_file(args)
    return True


def main():
    parser = argparse.ArgumentParser(description="Contribution Evaluation CLI")
    parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--user", type=str, required=True, help="User filter")
    parser.add_argument("--output", type=str, help="Output format (html, md, csv, text)", default="html")
    parser.add_argument("--out-file", type=str, default="", help="Output file path (for HTML/CSV/MD). If omitted a default name will be used")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML report in the default browser")
    parser.add_argument("--jira_project", type=str, required=True)
    parser.add_argument("--confluence_space", type=str, required=True)
    parser.add_argument("--github_org", type=str, required=True)
    parser.add_argument("--jira_token", type=str)
    parser.add_argument("--confluence_token", type=str)
    parser.add_argument("--github_token", type=str)
    parser.add_argument("--cache", type=str, default="", help="Path to SQLite cache file (optional)")
    # retry/backoff knobs: optional CLI overrides. Environment variables CONTRIB_MAX_RETRIES, CONTRIB_BACKOFF_BASE,
    # CONTRIB_BACKOFF_JITTER, CONTRIB_MAX_BACKOFF may also be used to set defaults.
    parser.add_argument("--max-retries", type=int, default=None, help="Maximum retry attempts for HTTP requests (overrides CONTRIB_MAX_RETRIES env)")
    parser.add_argument("--backoff-base", type=float, default=None, help="Base backoff seconds (overrides CONTRIB_BACKOFF_BASE env)")
    parser.add_argument("--backoff-jitter", type=float, default=None, help="Jitter seconds added to backoff (overrides CONTRIB_BACKOFF_JITTER env)")
    parser.add_argument("--max-backoff", type=float, default=None, help="Maximum backoff cap in seconds (overrides CONTRIB_MAX_BACKOFF env)")
    parser.add_argument("--cache-info", action="store_true", help="Show cache statistics (requires --cache or uses default cache.db)")
    parser.add_argument("--cache-clear", action="store_true", help="Clear the persistent cache (requires --cache or uses default cache.db)")
    parser.add_argument("--cache-list", action="store_true", help="List cache keys (requires --cache or uses default cache.db)")
    parser.add_argument("--cache-get", type=str, default="", help="Get a specific cache key value (requires --cache or uses default cache.db)")
    parser.add_argument("--cache-remove", type=str, default="", help="Remove a specific cache key (requires --cache or uses default cache.db)")
    parser.add_argument("--force", action="store_true", help="Force actions without confirmation (use with --cache-clear or --cache-remove)")
    parser.add_argument("--users-file", type=str, default="", help="Path to JSON file containing users list to render multi-user report")
    parser.add_argument("--summary-file", type=str, default="", help="Path to JSON file containing summary object (optional)")
    parser.add_argument("--export-all", action="store_true", help="When rendering a users-file, export HTML, MD, CSV and JSON copies automatically")
    parser.add_argument("--user-list-file", type=str, default="", help="Path to JSON file containing an array of user ids to aggregate from sources")
    args = parser.parse_args()

    # Apply runtime retry/backoff configuration (CLI flags take precedence over environment variables)
    try:
        configure_retry(max_retries=args.max_retries, backoff_base=args.backoff_base, backoff_jitter=args.backoff_jitter, max_backoff=args.max_backoff)
    except Exception:
        # don't fail the CLI if configure_retry is somehow invalid; continue with defaults
        pass

    # Resolve tokens (CLI flags take precedence over environment variables)
    _resolve_tokens(args, parser)

    cache = _handle_cache_actions(args)
    # if cache is None and cache-only action was performed, exit early
    if cache is None and (args.cache_info or args.cache_clear or args.cache_list or args.cache_get or args.cache_remove):
        return

    try:
        # If a user-list-file was provided, aggregate evaluations for those users and render a multi-user report
        if getattr(args, 'user_list_file', ''):
            if _aggregate_users_from_file(args, cache):
                return

        # If multi-user rendering was requested via users-file, handle it and exit early
        if _maybe_render_multi_user(args):
            return

        # default single-user pipeline
        fmt, rendered = run_pipeline(args, cache)
        write_output(fmt, rendered, args)
    finally:
        if cache:
            try:
                cache.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
