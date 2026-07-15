#!/usr/bin/env python3
"""Crawl recent GitHub issues into the local SQLite DB.

Fetches issues in descending number order (newest first) using the list
endpoint, which returns up to 100 per page in a single request -- far cheaper
than one API call per issue. Already-cached issues are skipped unless
--refresh is given.

    ./crawl.py                       # last 100 issues of pytorch/pytorch
    ./crawl.py --count 250           # last 250 issues (paginates as needed)
    ./crawl.py --slug pytorch/vision --count 100
    ./crawl.py --refresh             # overwrite cached rows too
"""
import argparse
import json
import subprocess
import sys
import time
from typing import Any, Dict, List

import fetch_issue as fi


def normalize_list_item(slug: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one item from the issues list endpoint.

    The list endpoint returns the same shape as the single-issue endpoint for
    the fields we store, so we reuse the same normalization contract.
    """
    return {
        "slug": slug,
        "number": raw["number"],
        "title": raw["title"],
        "user": raw["user"]["login"] if raw.get("user") else None,
        "user_id": raw["user"]["id"] if raw.get("user") else None,
        "state": raw["state"],
        "state_reason": raw.get("state_reason"),
        "labels": [label["name"] for label in raw.get("labels", [])],
        "body": raw.get("body"),
        "is_pull_request": "pull_request" in raw,
        "comments": raw.get("comments", 0),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "closed_at": raw.get("closed_at"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def fetch_page(slug: str, per_page: int, page: int) -> List[Dict[str, Any]]:
    """Fetch one page from the issues list endpoint (state=all, newest first)."""
    try:
        proc = subprocess.run(
            [
                "gh", "api",
                "-X", "GET",
                f"repos/{slug}/issues",
                "-f", "state=all",
                "-f", "sort=created",
                "-f", "direction=desc",
                "-f", f"per_page={per_page}",
                "-f", f"page={page}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit("error: `gh` CLI not found; install it and run `gh auth login`")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: gh api list failed for {slug} page {page}: {e.stderr.strip()}")
    return json.loads(proc.stdout)


def crawl(slug: str, count: int, db_path: str, refresh: bool) -> None:
    conn = fi.connect(db_path)
    per_page = min(100, count)
    seen = 0
    page = 1
    stored = skipped = 0

    while seen < count:
        batch = fetch_page(slug, per_page, page)
        if not batch:
            break  # ran out of issues

        for raw in batch:
            if seen >= count:
                break
            seen += 1
            issue = normalize_list_item(slug, raw)

            if not refresh and fi.read_cached(conn, slug, issue["number"]) is not None:
                skipped += 1
                continue

            fi.upsert(conn, issue)
            stored += 1
            kind = "PR " if issue["is_pull_request"] else "issue"
            print(f"  stored {kind} #{issue['number']}: {issue['title'][:70]}")

        page += 1

    print(
        f"\nDone: {seen} scanned, {stored} stored, {skipped} skipped (cached) "
        f"-> {db_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug", default="pytorch/pytorch", help="owner/repo (default: pytorch/pytorch)"
    )
    parser.add_argument(
        "--count", type=int, default=100, help="how many recent issues to fetch (default: 100)"
    )
    parser.add_argument("--db", default=fi.DEFAULT_DB, help=f"SQLite DB path (default: {fi.DEFAULT_DB})")
    parser.add_argument(
        "--refresh", action="store_true", help="overwrite cached rows instead of skipping them"
    )
    args = parser.parse_args()

    crawl(args.slug, args.count, args.db, args.refresh)


if __name__ == "__main__":
    main()
