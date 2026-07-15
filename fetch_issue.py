#!/usr/bin/env python3
"""Fetch a GitHub issue's metadata via the `gh` CLI, caching it in SQLite.

By default the issue is read from the local DB if present; the GitHub API is
only hit on a cache miss. Pass --refresh to force a re-fetch.

    ./fetch_issue.py 190041
    ./fetch_issue.py --slug pytorch/pytorch 190041
    ./fetch_issue.py --refresh 190041
    ./fetch_issue.py --db /path/to/issues.db 190041
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from typing import Any, Dict, Optional

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issues.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    slug            TEXT    NOT NULL,
    number          INTEGER NOT NULL,
    title           TEXT,
    user            TEXT,
    user_id         INTEGER,
    state           TEXT,
    state_reason    TEXT,
    labels          TEXT,   -- JSON array of label names
    body            TEXT,
    is_pull_request INTEGER NOT NULL DEFAULT 0,
    comments        INTEGER,
    created_at      TEXT,
    updated_at      TEXT,
    closed_at       TEXT,
    fetched_at      TEXT    NOT NULL,  -- when we last pulled it from GitHub
    PRIMARY KEY (slug, number)
);
"""

# Columns persisted in the issues table, in order. `labels` is stored as JSON
# text; everything else maps straight to the normalized dict.
_COLUMNS = [
    "slug", "number", "title", "user", "user_id", "state", "state_reason",
    "labels", "body", "is_pull_request", "comments", "created_at",
    "updated_at", "closed_at", "fetched_at",
]


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def row_to_issue(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a DB row back into the normalized issue dict."""
    issue = dict(row)
    issue["labels"] = json.loads(issue["labels"]) if issue["labels"] else []
    issue["is_pull_request"] = bool(issue["is_pull_request"])
    return issue


def read_cached(conn: sqlite3.Connection, slug: str, number: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM issues WHERE slug = ? AND number = ?", (slug, number)
    ).fetchone()
    return row_to_issue(row) if row else None


def upsert(conn: sqlite3.Connection, issue: Dict[str, Any]) -> None:
    record = dict(issue)
    record["labels"] = json.dumps(record["labels"])
    record["is_pull_request"] = int(record["is_pull_request"])
    placeholders = ", ".join(":" + c for c in _COLUMNS)
    conn.execute(
        f"INSERT OR REPLACE INTO issues ({', '.join(_COLUMNS)}) VALUES ({placeholders})",
        record,
    )
    conn.commit()


def fetch_from_github(slug: str, number: int) -> Dict[str, Any]:
    """Pull one issue from GitHub and normalize the fields we care about.

    Uses `gh api`, which reuses the user's existing GitHub auth and handles
    rate-limit headers for us.
    """
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{slug}/issues/{number}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit("error: `gh` CLI not found; install it and run `gh auth login`")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: gh api failed for {slug}#{number}: {e.stderr.strip()}")

    raw = json.loads(proc.stdout)

    # GitHub returns PRs through the issues endpoint too; flag them so callers
    # can choose to skip.
    is_pr = "pull_request" in raw

    return {
        "slug": slug,
        "number": raw["number"],
        "title": raw["title"],
        "user": raw["user"]["login"] if raw.get("user") else None,
        "user_id": raw["user"]["id"] if raw.get("user") else None,
        "state": raw["state"],
        # For closed issues this is "completed" or "not_planned" (i.e. the
        # closest thing GitHub exposes to a "close reason"). None while open.
        "state_reason": raw.get("state_reason"),
        "labels": [label["name"] for label in raw.get("labels", [])],
        "body": raw.get("body"),
        "is_pull_request": is_pr,
        "comments": raw.get("comments", 0),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "closed_at": raw.get("closed_at"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def get_issue(
    conn: sqlite3.Connection, slug: str, number: int, refresh: bool = False
) -> Dict[str, Any]:
    """Return an issue, preferring the cache unless refresh is requested."""
    if not refresh:
        cached = read_cached(conn, slug, number)
        if cached is not None:
            cached["_source"] = "cache"
            return cached

    issue = fetch_from_github(slug, number)
    upsert(conn, issue)
    issue["_source"] = "github"
    return issue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", type=int, help="issue number to fetch")
    parser.add_argument(
        "--slug", default="pytorch/pytorch", help="owner/repo (default: pytorch/pytorch)"
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="re-fetch from GitHub even if the issue is already cached",
    )
    args = parser.parse_args()

    conn = connect(args.db)
    issue = get_issue(conn, args.slug, args.number, refresh=args.refresh)

    source = issue.pop("_source", None)
    print(json.dumps(issue, indent=2, ensure_ascii=False))
    if source:
        print(f"# source: {source}", file=sys.stderr)


if __name__ == "__main__":
    main()
