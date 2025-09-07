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

If a token is not provided via CLI or environment, you will be prompted interactively.

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

