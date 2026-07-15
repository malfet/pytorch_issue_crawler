#!/usr/bin/env python3
"""Fetch a single GitHub issue's metadata via the `gh` CLI.

Practice target:
    ./fetch_issue.py 190041
    ./fetch_issue.py --slug pytorch/pytorch 190041
"""
import argparse
import json
import subprocess
import sys
from typing import Any, Dict


def fetch_issue(slug: str, number: int) -> Dict[str, Any]:
    """Return a normalized dict of the fields we care about for one issue.

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
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", type=int, help="issue number to fetch")
    parser.add_argument(
        "--slug", default="pytorch/pytorch", help="owner/repo (default: pytorch/pytorch)"
    )
    args = parser.parse_args()

    issue = fetch_issue(args.slug, args.number)
    # Truncate body in the human-readable summary; keep full JSON dumpable.
    print(json.dumps(issue, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
