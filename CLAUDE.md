# CLAUDE.md

Guidance for Claude Code when working in this repo.

## Issue deduplication

When you close (or recommend closing) any issue as a duplicate, you **must**
record the decision in `deduplication.md` at the repo root. Append one entry per
decision — never overwrite prior entries. Each entry records:

- Date (UTC).
- The pair: newer issue closed as a duplicate of the older issue (`#newer → #older`).
- Whether it was actually closed on GitHub, or only proposed.
- The reasoning (why they are duplicates, shared signal, similarity score if known).

This log is the audit trail for every dedup action, including ones a human
asked for. Before closing an issue, check `deduplication.md` so you don't
re-process a pair that was already decided.

**After closing any issue or PR, immediately re-fetch it so the local DB
reflects the new (closed) state** — run `./fetch_issue.py --refresh <number>`,
or just use `./close_duplicate.py --dup <newer> --keep <older>`, which closes
with a comment and re-fetches in one step.

### Which one to close

- **Issues:** close the newer issue as a duplicate of the older one.
- **Pull requests** (duplicate effort — two *different* authors implementing the
  same change; see `dedupe_candidates.py --prs`): pick which to keep by
  *mergeability*, not age. Check each PR's `EasyCLA` status check and its
  `updatedAt`:
  - If the **older** PR lacks a signed CLA (its `EasyCLA` check is not
    `SUCCESS`) **or** is stale, close the **older** PR in favor of the newer —
    the older one can't merge or has been abandoned. Judge staleness by the
    **last commit date** (latest commit's `committedDate`), *not* the PR's
    `updatedAt`: cc-lists and bot comments bump `updatedAt` without any real
    work, so a PR abandoned months ago can still look freshly "updated".
  - Otherwise, follow the issue pattern: close the **newer** PR as a duplicate
    of the older one.

  Never close an external contributor's PR silently — leave a comment pointing
  to the PR being kept so the authors can coordinate. Record the decision (which
  PR closed, which kept, and the CLA/recency reason) in `deduplication.md` just
  like issues.
