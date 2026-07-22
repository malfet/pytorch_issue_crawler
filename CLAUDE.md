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

### What counts as a duplicate (don't over-merge)

High text similarity is often just a shared *report template* across
**different functions** (e.g. a reporter's per-function catalog, or a
`torch.special.xlog1py` vs `xlogy` "CPU vs GPU" family). Those aren't clean 1:1
duplicates, but they don't have to be left scattered either — group such a
family under an **umbrella tracking issue** (see the `umbrella` skill). Reserve a
straight `close_duplicate.py` dedup for when the two reports share a genuine
root, i.e. one of:

- the **same function**, or an **alias** of it (e.g. `fliplr`/`flipud`/`rot90`
  all call `flip`);
- a **confirmed shared kernel / code path** — before merging distinct ops, open
  the actual source in `~/git/pytorch/pytorch` and verify they hit the same
  code (this session: `TensorTransformations.cpp`, `index_propagation.py`);
- an **identical error string / traceback location**; or
- the **same fixing PR** would resolve both.

For "CPU vs GPU inconsistency" / precision / overflow reports, verify against a
**float64 ground truth** before closing as expected behavior: confirm the diff
is at the dtype's ULP level (the report's tolerance is usually tighter than the
dtype allows), post the reference values in the comment, and note that which
backend is closer to truth can vary — neither being "wrong" is the point.

### Marking duplicates, labels, and stale local state

- **Marking:** use `./close_duplicate.py` for issues — it closes via the GraphQL
  `closeIssue(stateReason: DUPLICATE, duplicateIssueId: …)` mutation so the issue
  gets the real "marked as duplicate of #X" relationship. `gh issue close
  --reason` only exposes `completed`/`not_planned`, so never use it for a dup.
  **PRs have no duplicate state_reason** — close them with a linking comment.
- **Label hygiene:** when closing the newer issue, port any richer labels it
  carries onto the kept issue so triage signal isn't lost (done repeatedly here:
  `module: complex`, `module: correctness (silent)`, `module: inductor/sdpa`,
  `module: viewing and reshaping`). Verify a label name actually exists before
  adding — e.g. there is no `module: correctness`, only `module: correctness
  (silent)` (`gh label list --search`).
- **Stale state:** `crawl.py` only *inserts* new rows; it does **not** refresh
  the open/closed state of already-cached issues. So a candidate may show as
  `open` in the DB while it's since been closed on GitHub — always live-verify
  each pair with `gh` before acting.

### Proposing a close (show, don't make me open a browser)

Before closing anything as a duplicate (or as expected behavior), **present a
comparison table so the decision can be made without opening GitHub.** For each
issue/PR in the pair include:

- number + title,
- the body — or, when the report centers on a repro (fuzzer crashes, overflow
  reports, etc.), the **reproducer** and the resulting error/log message,
  pulled out separately so the two are easy to eyeball side by side.

Only close after the pair has been shown this way and confirmed. Prefer a
markdown table (or a short per-issue block when bodies are long); the goal is
that everything needed to judge the duplicate is on screen in the terminal.

### Old bug reports — try to reproduce before closing

When a candidate is an **old** bug report with a concrete reproducer, don't just
reason about it — **actually try to reproduce it on the current PyTorch** before
deciding:

1. Create a throwaway venv and install the **latest released** PyTorch — always
   `pip install --upgrade torch` (never pin to the old version the issue was
   filed against; the whole point is to check the current release). A CPU build
   is fine unless the repro specifically needs CUDA/MPS/ROCm. Note the exact
   version you got (`torch.__version__`).
2. Run the issue's reproducer verbatim on that latest release.
3. If it **no longer reproduces** *and* there are **no recent comments**
   indicating it's still relevant, close the issue as **fixed** (state_reason
   `completed`, i.e. `gh issue close --reason completed`) with a comment noting
   that you cannot reproduce the behavior on the latest PyTorch, and give the
   exact version you tested.

Caveats: only claim "can't reproduce" if you could genuinely run the repro — if
it needs hardware you don't have, say so instead of closing. If it still
reproduces, leave it open (and say so). Record the outcome in `deduplication.md`.

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
