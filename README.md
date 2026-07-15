# pytorch_issue_crawler

Work in progress. Slowly collects GitHub issues (and PRs) for a repo into a
local SQLite DB, preserving title, reporter, number, body, labels, state, and
close reason.

## Scripts

- `fetch_issue.py` — fetch a single issue, cached in SQLite. Reads from the DB
  by default; only hits the API on a miss or with `--refresh`.
  ```
  ./fetch_issue.py 190041
  ./fetch_issue.py --slug pytorch/pytorch --refresh 190041
  ```
- `crawl.py` — bulk backfill via the issues list endpoint (cursor-based
  pagination, 100/page). Skips already-cached rows.
  ```
  ./crawl.py --count 1000          # newest 1000 items
  ./crawl.py --count 200000        # full history back to #1
  ```

Both use the `gh` CLI for auth (`gh auth login`), so they run against the
authenticated 5000 req/hr limit. The DB (`issues.db`) is gitignored.

## Notes / TODO

- Issues and PRs share GitHub's number space; PRs are stored too, tagged with
  `is_pull_request`.
- `state_reason` captures GitHub's close reason (`completed` / `not_planned` /
  `duplicate`). Free-text close context lives in issue timelines and is not yet
  fetched.
- Incremental `--update` mode (page forward from newest cached) is not yet
  implemented; runs currently re-scan from newest each time.
