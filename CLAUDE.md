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

**Serial-reporter batches → collapse, don't merge 1:1.** When a *single author*
files ≥3 same-template reports in a short window (differing only by API/function
name or cosmetic framing), treat the batch as an **umbrella/collapse** case, not
N separate pairwise dedups: pick one canonical and fold the rest into it. This
is exactly how maintainers handled the prior-art batches — `Blooming-Tree`'s
nine `torch.compile()` reports #172207–#172212 ("completely breaks model
outputs" / "Systemic inconsistency", filed minutes apart) and
`ChaitanyaRS06`'s `inf`-across-CPU/GPU family #154520/#154521/#154726/#154727/
#154730/#154736 — closing the batch against one root (#172206, #154474) rather
than diagnosing each.

**Known-canonical routing.** Some complaints recur endlessly and already have a
standing tracking issue — route new instances there instead of re-diagnosing.
Verify the target is still open before reusing it. Current standing canonicals:

- **numpy-indexing compat** (indexing a tensor with a numpy array, or mixing
  boolean + integer indices, behaving unlike numpy) → **#119548** (maintainers
  routed #22013/#65218/#100080/#60261 here).
- **CPU-vs-GPU `inf`/`nan` edge-case inconsistency** → **#154474**.
- **Missing shape/size checks → out-of-bounds tensor access** (ASAN
  `heap-buffer-overflow`, compute-sanitizer `illegal memory access`, `SIGSEGV`
  or `SIGFPE` from a degenerate/out-of-domain argument) → ☂️ **#195547**. Covers
  CPU *and* CUDA/MPS, and divide-by-zero as well as OOB — see the
  divide-by-zero note below. 119 issues folded in as of 2026-09-17; the
  candidate sweep and per-group review live in
  `malfet/pytorch_issue_crawler#1`. **Not** in scope: `TORCH_INTERNAL_ASSERT`
  on invalid input (a check *does* fire, it is just the wrong kind — that wants
  its own umbrella), and checks that exist but compute the wrong bound
  (e.g. #136719's `div_rtn` int truncation), which stay open on their own merits.

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
  (silent)` (`gh label list --search`). **Do not add `actionable` unless the
  maintainer explicitly asks** — it asserts a confirmed, worth-doing fix, which
  is a human triage call, not something to port or infer (and don't port it
  across a dedup either). For fuzzer/OOB missing-validation reports prefer
  `module: error checking`.
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

   Build the venv with a **modern Homebrew Python**
   (`/opt/homebrew/bin/python3.12` or `python3.13`), *not* the system
   `/usr/bin/python3` — that's 3.9 (EOL) and caps `torch` at 2.8.0, whereas
   3.12/3.13 install the real latest (e.g. 2.13.0). If a `pip` bootstrap in the
   venv misbehaves, run `python -m ensurepip --upgrade` then use `python -m pip`.

   **Exception — validate against nightly instead** when the issue is **too
   recent** for the latest release to include a fix, *and* a developer/the report
   references a nightly (e.g. "fixed on nightly", "regression in the 2.13 RC/
   nightly"). In that case install the nightly build:
   ```
   pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cpu
   ```
   (swap `cpu` for `cu124`/etc. if the repro needs a GPU). Always record which
   channel you used — release vs nightly — and the exact version.
2. Run the issue's reproducer verbatim on that build.
3. If it **no longer reproduces** *and* there are **no recent comments**
   indicating it's still relevant, close the issue as **fixed** (state_reason
   `completed`, i.e. `gh issue close --reason completed`) with a comment noting
   that you cannot reproduce the behavior on the latest PyTorch, and give the
   exact version you tested.

Caveats: only claim "can't reproduce" if you could genuinely run the repro — if
it needs hardware you don't have, say so instead of closing. If it still
reproduces, leave it open (and say so).

**Where to record the outcome depends on the decision:**

- If you **closed** the issue (fixed / duplicate / won't-fix / expected
  behavior), it goes in `deduplication.md` — that file is the audit trail of
  *close* actions only.
- If you **verified it and left it open** (still reproduces, improved-but-not-
  fixed, hardware-specific, can't-repro-but-kept-open-due-to-recent-reports),
  record it in **`still_valid.md`** instead. Keeping the "kept open" outcomes in
  a separate file stops them from cluttering the close audit trail, and gives a
  standing list of issues already confirmed live (so a later pass doesn't
  re-verify them from scratch). Use the same table shape: date, issue + short
  status, how you verified, and the reasoning / minimal repro. Before
  re-verifying an old issue, check `still_valid.md` first.

**Sanitizer/OOB reports — "completes silently" is NOT proof of safety.** For
memory-safety reports (compute-sanitizer / ASAN "Invalid `__global__` read/
write", heap-buffer-overflow, OOB), a *bare* run only surfaces the bug when the
bad access happens to hit an unmapped page and faults. So on a plain run without
a sanitizer, only two verdicts are trustworthy:

- a **hard crash** (SIGSEGV/SIGBUS, i.e. exit 139/138 or a negative returncode),
  and
- a **clean `TORCH_CHECK`/`RuntimeError`** (real validation exists).

A run that "completes with no error" is **inconclusive**, not "safe / the backend
is tolerant" — the OOB may still be there, just landing in mapped memory where
nothing is watching. This is exactly why the original CUDA report needed
compute-sanitizer to see it at all. Corollary for triage/severity: **if the only
evidence of the bug is a compute-sanitizer trace** (no Python exception, no user-
visible crash), it is probably not visible to a normal user either — treat it as
lower urgency than a hard crash, and don't infer "CPU is fine" from a bare CPU
run. To actually probe CPU memory safety you need an ASAN build or valgrind, not
`python repro.py`.

**This whole class = missing input validation.** Fuzzer OOB reports that pass an
out-of-domain integer arg (index/dilation/padding/size near `INT32_MAX`/`INT64`
limits) or a degenerate zero-size tensor (→ null `data_ptr`) into a kernel with
no bounds/shape `TORCH_CHECK` are all one root cause. Tag them
`module: error checking` (+ `topic: fuzzer`), not `actionable`.

**Divide-by-zero / FPE belongs to the same class — do not split it off.** A
`SIGFPE`, "Floating point exception (core dumped)", or integer
divide-by-zero in a kernel is usually the *same* missing boundary check as an
out-of-bounds read, just with a different symptom: an unvalidated **empty or
zero-size tensor** (or a zero `groups`/`num_bins`/`kernel_size`-style argument)
reaches arithmetic that assumes the value is positive. Whether the bad value
lands on a divide or on a pointer offset is an accident of the kernel, not a
difference in root cause — so **don't reason from the symptom** to a separate
bug class. Prior art: #141219 (`_scaled_dot_product_flash_attention_for_cpu`
FPE) was folded into the missing-shape-checks umbrella **#195547** on exactly
this ground, after it had first been wrongly excluded as "an unchecked zero
divisor, not a size contract."

The fix is correspondingly cheap, which is worth saying in triage: these are
normally resolved by a **`TORCH_CHECK` on the degenerate input**, or by an
**early return** of the correct empty/identity result when an empty tensor is a
legitimate input (many ops should simply return empty rather than divide). That
makes them good first-contributor material — but the same caveat as the rest of
the class applies: prefer a **device-agnostic check ahead of dispatch** over one
patch per kernel, and don't add `actionable` without the maintainer asking.

Exclusions that *do* hold: a Python-level `ZeroDivisionError` raised in
frontend/scheduler code (e.g. an LR scheduler accepting `factor=0`) is ordinary
argument validation in Python, not a kernel boundary check; likewise
hardware/driver-specific FPE reports. Keep those out of the umbrella.

### Which one to close

- **Issues:** default to closing the newer issue as a duplicate of the older
  one — **but the canonical is whichever issue holds the resolution, not just
  the elder.** If a *newer* issue carries more of the signal (a linked/landed
  fixing PR, richer labels, more diagnosis, or is already `completed`), keep
  that one and close the older, less-detailed report against it. Prior art:
  maintainers closed #154235 (older) as a duplicate of the newer #163630
  because #163630 held the fix. Only fall back to pure age when the two are
  otherwise equal.
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
