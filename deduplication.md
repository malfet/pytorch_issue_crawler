# Deduplication log

Audit trail of duplicate-issue decisions. Newest entries at the bottom. See
`CLAUDE.md` for the recording policy and `dedupe_candidates.py` for how
candidates are generated.

| Date (UTC) | Decision | Action | Reasoning |
|------------|----------|--------|-----------|
| 2026-07-15 | #127009 → duplicate of #126947 | Closed on GitHub (`not planned`), commented "Duplicate of #126947" | Same author (`hyperkai`), filed the same day (~18h apart). Both report `dsplit()` with `indices_or_sections=` not working while the positional form works — #127009 is a reworded restatement of #126947. Cosine similarity 0.89; shared terms: `indices_or_sections`, `dsplit`, `torch.dsplit`, `sections`. |
| 2026-07-16 | PR #180891 → duplicate of PR #190014 (kept #190014) | Closed #180891 on GitHub, commented pointing to #190014 | Duplicate-effort PRs (different authors) for the same `rocm_smi`→`amd_smi` migration; #190014 is an explicit rebased sequel of #180891. Both CLA `SUCCESS`. Older #180891's **last commit** was 2026-04-20 (stale ~3 months) vs. #190014's 2026-07-15 and `MERGEABLE` — so under the PR rule the older/stale one is closed in favor of the newer active one. Note: #180891's `updatedAt` (2026-07-13) was misleading cc/bot comment noise; staleness was judged by last commit date. |
| 2026-07-17 | #107543 and #107556 (dmc1778) — closed **both**, not one-as-dup | Added `module: nn` label to both; closed both `not planned` with an "expected behavior" comment | Same case (surfaced as a near-duplicate pair, cosine 0.73): both call `AdaptiveAvgPool2d(~1.25e12)`, requesting a ~1.25e12² output whose `numel` overflows int64 (`numel: integer multiplication overflow`). Not an operator bug — nonsensical output size can't be allocated. Per maintainer decision, closed both as expected behavior rather than deduping one into the other. |
