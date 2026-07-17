#!/usr/bin/env python3
"""Close a duplicate issue/PR on GitHub and re-sync its row in the local DB.

Wraps the manual "comment, close, then refresh the cache" sequence so the DB
never drifts out of sync with GitHub after a dedup action. Works for both
issues and pull requests (auto-detected).

    ./close_duplicate.py --dup 127009 --keep 126947
    ./close_duplicate.py --dup 180891 --keep 190014 --comment "Superseded rebase"
    ./close_duplicate.py --dup 127009 --keep 126947 --dry-run

After closing, remember to record the decision in deduplication.md (see
CLAUDE.md) — this script does not write the log, because each entry needs the
human-authored reasoning.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "issues.db")


def _gh(args: list[str]) -> str:
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit("error: `gh` CLI not found; install it and run `gh auth login`")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: gh {' '.join(args)} failed: {e.stderr.strip()}")
    return proc.stdout.strip()


def is_pull_request(slug: str, number: int) -> bool:
    out = _gh(["api", f"repos/{slug}/issues/{number}", "--jq", 'has("pull_request")'])
    return out == "true"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dup", type=int, required=True, help="number to close as a duplicate")
    ap.add_argument("--keep", type=int, required=True, help="number to keep (the canonical one)")
    ap.add_argument("--slug", default="pytorch/pytorch")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--comment", default=None,
                    help="override the default 'Duplicate of #<keep>' comment")
    ap.add_argument("--reason", default="not planned", choices=["not planned", "completed"],
                    help="close reason for issues (default: not planned)")
    ap.add_argument("--dry-run", action="store_true", help="print what would happen and stop")
    args = ap.parse_args()

    comment = args.comment or (
        f"Duplicate of #{args.keep}. Closing in favor of the earlier report; "
        f"please follow #{args.keep} for updates."
    )

    is_pr = is_pull_request(args.slug, args.dup)
    kind = "pr" if is_pr else "issue"

    if args.dry_run:
        print(f"[dry-run] would close {args.slug}#{args.dup} ({kind}) as duplicate of "
              f"#{args.keep}")
        print(f"[dry-run] comment: {comment}")
        print(f"[dry-run] then: ./fetch_issue.py --refresh {args.dup}")
        return

    if is_pr:
        # `gh pr close` has no --reason (PRs don't carry a state_reason).
        print(_gh(["pr", "close", str(args.dup), "--repo", args.slug, "--comment", comment])
              or f"Closed PR #{args.dup}")
    else:
        print(_gh(["issue", "close", str(args.dup), "--repo", args.slug,
                   "--reason", args.reason, "--comment", comment])
              or f"Closed issue #{args.dup}")

    # Rule (see CLAUDE.md): force a re-fetch so the DB reflects the closed state.
    print(f"Refreshing local cache for #{args.dup} ...")
    subprocess.run(
        [sys.executable, os.path.join(HERE, "fetch_issue.py"),
         "--slug", args.slug, "--db", args.db, "--refresh", str(args.dup)],
        check=True, stdout=subprocess.DEVNULL,
    )
    print(f"Done. Remember to log #{args.dup} -> #{args.keep} in deduplication.md.")


if __name__ == "__main__":
    main()
