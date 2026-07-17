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
import json
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


def _node(slug: str, number: int) -> dict:
    owner, name = slug.split("/", 1)
    out = _gh(["api", "graphql", "-f", f"""query=
    {{ repository(owner:"{owner}", name:"{name}") {{
        issueOrPullRequest(number:{number}) {{
          __typename
          ... on Issue {{ id }}
          ... on PullRequest {{ id }}
        }} }} }}""", "--jq", ".data.repository.issueOrPullRequest | {typename:.__typename, id:.id}"])
    return json.loads(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dup", type=int, required=True, help="number to close as a duplicate")
    ap.add_argument("--keep", type=int, required=True, help="number to keep (the canonical one)")
    ap.add_argument("--slug", default="pytorch/pytorch")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--comment", default=None,
                    help="override the default 'Duplicate of #<keep>' comment")
    ap.add_argument("--dry-run", action="store_true", help="print what would happen and stop")
    args = ap.parse_args()

    comment = args.comment or (
        f"Duplicate of #{args.keep}. Closing in favor of #{args.keep}; "
        f"please follow it for updates."
    )

    dup = _node(args.slug, args.dup)
    is_pr = dup["typename"] == "PullRequest"
    kind = "PR" if is_pr else "issue"

    if args.dry_run:
        how = ("gh pr close (no duplicate state_reason exists for PRs)" if is_pr
               else "GraphQL closeIssue stateReason=DUPLICATE, duplicateIssueId=#%d" % args.keep)
        print(f"[dry-run] would close {args.slug}#{args.dup} ({kind}) as duplicate of "
              f"#{args.keep} via {how}")
        print(f"[dry-run] comment: {comment}")
        print(f"[dry-run] then: ./fetch_issue.py --refresh {args.dup}")
        return

    if is_pr:
        # PRs don't carry a state_reason, so there's no native "duplicate"
        # marker — close with a comment that links the kept PR.
        print(_gh(["pr", "close", str(args.dup), "--repo", args.slug, "--comment", comment])
              or f"Closed PR #{args.dup}")
    else:
        # Issues: post the explanatory comment, then close with the real
        # DUPLICATE state_reason + a "marked as duplicate of #keep" link.
        keep = _node(args.slug, args.keep)
        _gh(["issue", "comment", str(args.dup), "--repo", args.slug, "--body", comment])
        _gh(["api", "graphql", "-f", """query=
        mutation($dup:ID!, $keep:ID!) {
          closeIssue(input:{issueId:$dup, stateReason:DUPLICATE, duplicateIssueId:$keep}) {
            issue { number stateReason }
          }
        }""", "-f", f"dup={dup['id']}", "-f", f"keep={keep['id']}"])
        print(f"Closed issue #{args.dup} as DUPLICATE of #{args.keep}")

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
