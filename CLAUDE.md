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
