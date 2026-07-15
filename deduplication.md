# Deduplication log

Audit trail of duplicate-issue decisions. Newest entries at the bottom. See
`CLAUDE.md` for the recording policy and `dedupe_candidates.py` for how
candidates are generated.

| Date (UTC) | Decision | Action | Reasoning |
|------------|----------|--------|-----------|
| 2026-07-15 | #127009 → duplicate of #126947 | Closed on GitHub (`not planned`), commented "Duplicate of #126947" | Same author (`hyperkai`), filed the same day (~18h apart). Both report `dsplit()` with `indices_or_sections=` not working while the positional form works — #127009 is a reworded restatement of #126947. Cosine similarity 0.89; shared terms: `indices_or_sections`, `dsplit`, `torch.dsplit`, `sections`. |
