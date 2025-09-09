# Contribution Evaluation Utility

This Python utility evaluates the contributions of an individual team member over a specified time period, aggregating data from Jira, Confluence, and GitHub. It provides a quantitative summary of involvement, significance, effectiveness, complexity, time required, and the number of bugs/fixes related to each contribution.

## Features
- Aggregates contributions from Jira, Confluence, and GitHub.
- Evaluates multiple metrics for each contribution.
- Supports API tokens via environment variables or CLI arguments.
- Handles edge cases and non-admin API access.
- Designed for a single Jira project, Confluence space, and GitHub organization.
- Date range can be specified for monthly or quarterly evaluations.
- Includes robust unit tests.
- **Persistent SQLite cache** to speed up repeated queries.

## Setup

### 1. Install Dependencies
```sh
pip install -r requirements.txt
```

### 2. Set Environment Variables (optional)
You can provide API tokens via environment variables or CLI arguments.  
Environment variable names:
- `JIRA_TOKEN`
- `CONFLUENCE_TOKEN`
- `GITHUB_TOKEN`

Example:
```sh
export JIRA_TOKEN=your_jira_token
export CONFLUENCE_TOKEN=your_confluence_token
export GITHUB_TOKEN=your_github_token
```

## Usage

Run the utility from the command line:
```sh
python main.py --user <username> --start <YYYY-MM-DD> --end <YYYY-MM-DD>
```

Optional arguments (default values shown):
- `--jira_project` (default: `MCLD`)
- `--confluence_space` (default: `SMARTINT`)
- `--github_org` (default: `comcast-mesh`)
- `--jira_token` (or set `JIRA_TOKEN`)
- `--confluence_token` (or set `CONFLUENCE_TOKEN`)
- `--github_token` (or set `GITHUB_TOKEN`)
- `--cache` (default: `True`)

If a token is not provided via CLI or environment, you will be prompted interactively.

### Cache Usage

The utility supports a persistent SQLite cache to speed up data retrieval. Provide a file path to enable caching; omit the flag to disable it.

#### CLI Example
```sh
# Enable persistent cache stored at ./cache.db
python cli.py --user <username> --start <YYYY-MM-DD> --end <YYYY-MM-DD> --cache ./cache.db --output html --out-file ./out/report.html

# Disable caching by omitting the --cache flag
python cli.py --user <username> --start <YYYY-MM-DD> --end <YYYY-MM-DD>
```

#### Programmatic Example
```python
from storage.cache import Cache
from ingest.jira import JiraClient
from ingest.confluence import ConfluenceClient
from ingest.github import GitHubClient

cache = Cache('cache.db')  # persistent SQLite cache
jira = JiraClient(token, project_key, cache=cache)
confluence = ConfluenceClient(token, space_key, cache=cache)
github = GitHubClient(token, org, cache=cache)
```

## Programmatic Rendering (public API)

When rendering HTML programmatically, prefer the public convenience function render_html exported by report.renderer. This wrapper uses the Jinja2 template when available and falls back to a simple HTML generator.

Example:

```python
from scoring.metrics import compute_metrics
from report.renderer import render_html

# given a list of normalized ContributionEvent objects `events`:
metrics_res = compute_metrics(events)
evaluation = metrics_res.get('evaluation_result')
metrics = metrics_res.get('metrics')

html = render_html(result=evaluation, metrics=metrics)
with open('out/report.html', 'w', encoding='utf-8') as f:
    f.write(html)
```

Note: render_html is the recommended public API for programmatic HTML rendering. If you need Markdown or CSV output programmatically, use render_markdown() and render_csv() in report.renderer.

+Tuning presets (programmatic usage)
+
+The configuration file config/weights.yaml includes a presets section (balanced, time_focused, quality_focused). You can load a named preset programmatically and obtain a merged weights mapping using the helper functions in scoring.utils.
+
+Example:
+
+```python
+from scoring.utils import list_presets, load_preset
+
+# show available presets
+print(list_presets())
+
+# load a merged preset (base weights merged with the named preset)
+weights = load_preset('quality_focused')
+
+# now pass `weights` to compute_weighted_score(metrics, weights)
+```
+
+Notes:
+- load_preset(...) reads config/weights.yaml and requires PyYAML to be installed to read presets; if PyYAML is not available, use load_weights() and manually edit/merge the YAML.
+- load_preset returns the base weights merged with the preset overrides so you can pass the result directly to the scoring functions.

Additional programmatic helpers

If you prefer Markdown or CSV output (for embedding in other systems, email bodies, or quick snapshots), the renderer exposes two convenience functions:

- render_markdown(result: EvaluationResult) -> str: returns a Markdown-formatted summary suitable for inclusion in README snippets or Markdown-capable viewers.
- render_csv(result: EvaluationResult) -> str: returns CSV text (header + single row) useful for importing into spreadsheets or reporting pipelines.

Examples:

```python
from scoring.metrics import compute_metrics
from report.renderer import render_markdown, render_csv

metrics_res = compute_metrics(events)
evaluation = metrics_res.get('evaluation_result')

md = render_markdown(evaluation)
print(md)  # safe to include in Markdown files or previews

csv = render_csv(evaluation)
print(csv)  # header + row; can be written to a .csv file
```

These helpers are lightweight and do not require Jinja2 or any template files.

## Evaluation Criteria

The utility evaluates each contribution using the following metrics:

| Metric         | Jira Issues/Stories/Bugs                | Confluence Pages                | GitHub PRs/Commits/Issues      |
|----------------|----------------------------------------|---------------------------------|-------------------------------|
| **Involvement**    | Number of issues, stories, or bugs assigned/reported | Number of pages created/updated | Number of PRs, commits, or issues authored |
| **Significance**   | 5 for Story, 2 for Bug/Task         | 2 for documentation             | 5 for PR, 2 for Issue/Commit  |
| **Effectiveness**  | 1 if no bugs reported, 0 otherwise   | Always 1 (no bugs for docs)     | 1 if not a bug, 0 if bug      |
| **Complexity**     | 5 for Story, 2 for Bug, 3 for Task  | 2 (assumed for docs)            | 5 for PR, 3 for Commit, 2 for Issue |
| **Time Required**  | `timespent` field (hours)           | 0.5 hours per page (assumed)    | 2 hours per PR, 1 per Commit, 0.5 per Issue (assumed) |
| **Bugs/Fixes**     | 1 for Bug, 0 otherwise              | 0                               | 1 if 'bug' in issue title, 0 otherwise |

### Details
- **Jira:**  
  - Issues, stories, and bugs are fetched for the user in the specified project and date range.
  - Complexity and significance are based on issue type.
  - Time required uses the `timespent` field if available.
  - Bugs/fixes are counted for issues of type 'Bug'.

- **Confluence:**  
  - Pages created or updated by the user in the specified space and date range.
  - Complexity and significance are assumed to be low (documentation).
  - Time required is estimated at 0.5 hours per page.
  - No bugs/fixes are counted for documentation.

- **GitHub:**  
  - PRs, commits, and issues authored by the user in all org repos and date range.
  - Complexity and significance are highest for PRs, moderate for commits, lowest for issues.
  - Time required is estimated based on type.
  - Bugs/fixes are counted if 'bug' appears in the issue title.

## Project Structure

```
contrib_eval/
├── main.py                # CLI entry point
├── evaluator.py           # Evaluation logic and metrics
├── jira_client.py         # Jira API client
├── confluence_client.py   # Confluence API client
├── github_client.py       # GitHub API client
├── models.py              # Data models
├── utils.py               # Utility functions
├── requirements.txt       # Python dependencies
├── instructions/
│   ├── prompt.md          # Project prompt
│   └── python.instructions.md # Coding conventions
└── tests/
    └── test_evaluator.py  # Unit tests
```

## Testing

Run the unit tests to verify correctness:
```sh
python -m unittest tests/test_evaluator.py
```

Tests cover:
- No contributions (edge case)
- Mixed contributions from all sources
- High complexity and multiple bugs

## Notes
- The utility is designed for non-admin API access and will gracefully handle missing or invalid data.
- All logic follows Python best practices (PEP 8, PEP 257) and is thoroughly documented.
- You can extend the evaluation criteria or add more sources as needed.

## Contact
For questions or feature requests, please open an issue or contact the maintainer.

## Multi-user exports / CI & tests note

A multi-user export path was added to the CLI. You can render a multi-user report from a JSON users file via the `--users-file` and optional `--summary-file` flags. To write HTML, Markdown, CSV and JSON exports in one go, use the `--export-all` flag and provide an `--out-file` base name:

```sh
python cli.py --start 2025-01-01 --end 2025-01-31 --user dummy --users-file ./users.json --export-all --out-file ./out/report_multi
```

The project includes a small CLI integration test (tests/test_cli_integration.py) that exercises this multi-user export path by invoking the CLI entry point (`cli.main`) with a temporary users file.

Continuous integration (GitHub Actions) is configured to run the test suite and generate a coverage report on pushes and pull requests (see .github/workflows/ci.yml).

If you need to reproduce coverage locally, install the test extras and run:

```sh
pip install pytest pytest-cov
pytest --maxfail=1 -q --disable-warnings --cov=report --cov-report=html:htmlcov
```

This will write HTML coverage into the htmlcov/ directory.

[![codecov](https://codecov.io/gh/larryf1/contrib_eval/branch/main/graph/badge.svg)](https://codecov.io/gh/larryf1/contrib_eval)

Note: if your repo is private you may need to provide a Codecov token. Add it to GitHub Secrets as CODECOV_TOKEN and the CI action will use it. The CI workflow uploads coverage.xml to Codecov and publishes an HTML report as an artifact.

Lint configuration

This repository includes lint configuration to make CI results consistent:
- pyproject.toml (ruff/black settings)
- .flake8 (flake8 settings)

## Aggregating multiple users from sources (--user-list-file)

In addition to rendering a provided users JSON file (`--users-file`) which contains per-user evaluation objects, the CLI supports aggregating events for a list of user IDs fetched from the configured data sources (Jira, Confluence, GitHub).

- `--users-file` expects a JSON array of user objects (display_name, evaluation, links) and will render reports for those entries directly.
- `--user-list-file` expects a JSON array of user IDs (strings). The CLI will fetch each user's events from Jira/Confluence/GitHub, normalize and aggregate them, compute metrics for the combined set, and render a multi-user HTML report.

Examples

Render a provided users file (user objects with evaluations):
```sh
python cli.py \
  --start 2025-01-01 --end 2025-01-31 \
  --user dummy \
  --users-file ./users.json \
  --export-all --out-file ./out/report_multi \
  --jira_project MCLD --confluence_space SMARTINT --github_org org \
  --jira_token $JIRA_TOKEN --confluence_token $CONFLUENCE_TOKEN --github_token $GITHUB_TOKEN
```

Aggregate events for a list of user IDs and produce a combined report:
```sh
python cli.py \
  --start 2025-01-01 --end 2025-01-31 \
  --user dummy \
  --user-list-file ./user_ids.json \
  --out-file ./out/aggregated_report.html \
  --jira_project MCLD --confluence_space SMARTINT --github_org org \
  --jira_token $JIRA_TOKEN --confluence_token $CONFLUENCE_TOKEN --github_token $GITHUB_TOKEN
```

Demo script

A convenience demo script is provided that demonstrates reading a users JSON file and writing a combined multi-user HTML report:

- demo_render_users_file.py — reads `demo_users.json` (creates a sample if missing) and writes `demo_report_users_file.html`.

Notes

- The aggregation path (`--user-list-file`) fetches data live from the configured APIs, so API tokens and network access are required.
- The renderer will use the Jinja2 templates (report/templates/report.html.j2 and section_user.md.j2) when available; install Jinja2 with `pip install jinja2` to get templated HTML/Markdown output.
