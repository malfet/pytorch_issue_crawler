#!/usr/bin/env python3
"""Fetch the published Parquet snapshot from a GitHub release and rebuild the
local SQLite DB from it.

By default it downloads issues.parquet from the latest release of
malfet/pytorch_issue_crawler, then loads it into issues.db. Use a local
Parquet file with --parquet to skip the download.

    ./restore_db.py                          # download latest release + build issues.db
    ./restore_db.py --tag v1                  # a specific release tag
    ./restore_db.py --parquet issues.parquet  # load an existing local file
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

import pyarrow.parquet as pq

import fetch_issue as fi

DEFAULT_REPO = "malfet/pytorch_issue_crawler"
ASSET_NAME = "issues.parquet"


def download_asset(repo: str, tag: str, dest_dir: str) -> str:
    """Download the Parquet asset from a release via `gh release download`."""
    cmd = ["gh", "release", "download"]
    if tag:
        cmd.append(tag)
    cmd += ["--repo", repo, "--pattern", ASSET_NAME, "--dir", dest_dir, "--clobber"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit("error: `gh` CLI not found; install it and run `gh auth login`")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: gh release download failed: {e.stderr.strip()}")
    return os.path.join(dest_dir, ASSET_NAME)


def load_parquet(parquet_path: str, db_path: str) -> int:
    """Rebuild the issues table in db_path from a Parquet file."""
    conn = fi.connect(db_path)  # ensures schema exists
    conn.execute("DELETE FROM issues")

    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    for r in rows:
        # labels come back as a Python list; store as JSON text to match schema.
        r["labels"] = json.dumps(list(r["labels"]) if r["labels"] is not None else [])
        r["is_pull_request"] = int(bool(r["is_pull_request"]))

    placeholders = ", ".join(":" + c for c in fi._COLUMNS)
    conn.executemany(
        f"INSERT OR REPLACE INTO issues ({', '.join(fi._COLUMNS)}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()
    return len(rows)


def bootstrap_if_missing(db_path: str, repo: str = DEFAULT_REPO, tag: str = "") -> bool:
    """If db_path doesn't exist, seed it from the release snapshot.

    Returns True if a download happened. On any failure (no release yet, no
    network) it warns and returns False so callers can proceed with an empty
    DB rather than aborting.
    """
    if os.path.exists(db_path):
        return False
    print(
        f"local DB {db_path} not found; seeding from {repo} release snapshot...",
        file=sys.stderr,
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = download_asset(repo, tag, tmp)
            n = load_parquet(path, db_path)
        print(f"seeded {n} rows from release into {db_path}", file=sys.stderr)
        return True
    except SystemExit as e:
        # download_asset/load_parquet call sys.exit on failure; downgrade that
        # to a warning so bootstrapping stays best-effort.
        print(f"warning: could not seed from release ({e}); starting empty", file=sys.stderr)
        if os.path.exists(db_path):
            os.remove(db_path)  # drop any half-written file
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"release repo (default: {DEFAULT_REPO})")
    parser.add_argument("--tag", default="", help="release tag (default: latest)")
    parser.add_argument("--db", default=fi.DEFAULT_DB, help=f"SQLite DB to build (default: {fi.DEFAULT_DB})")
    parser.add_argument(
        "--parquet", default="", help="use a local Parquet file instead of downloading"
    )
    args = parser.parse_args()

    if args.parquet:
        n = load_parquet(args.parquet, args.db)
        print(f"Loaded {n} rows from {args.parquet} into {args.db}")
        return

    with tempfile.TemporaryDirectory() as tmp:
        path = download_asset(args.repo, args.tag, tmp)
        n = load_parquet(path, args.db)
    print(f"Loaded {n} rows from {args.repo} release into {args.db}")


if __name__ == "__main__":
    main()
