---
name: umbrella
description: Group a cluster of highly-similar PyTorch issues under an umbrella tracking issue (🌂). Finds an existing umbrella issue or creates a new one, lists the members in it, and consolidates them. Use when dedupe_candidates.py surfaces a family of near-identical reports (per-function catalogs, per-model crashes, "CPU vs GPU" families) that are better tracked together than closed one-by-one or left scattered.
---

# Umbrella: group highly-similar issues

Some clusters aren't a clean 1:1 duplicate but are clearly the *same pattern*
across slightly different surfaces (e.g. one report per function, per model, or
per op). Instead of leaving them scattered, gather them under a single
**umbrella tracking issue** whose title carries a 🌂 emoji.

This complements `close_duplicate.py` (which handles true 1:1 duplicates) and
follows the same rules in `CLAUDE.md` (show a table before acting, record the
outcome in `deduplication.md`, live-verify state with `gh`).

## Steps

1. **Assemble the cluster.** Either take issue numbers the user gives, or run
   `./dedupe_candidates.py --threshold 0.5 --df-cap 40` and pick a tight
   same-pattern family. **Live-verify** each member is still open (`gh issue
   view <n>`) — the local DB can be stale.

2. **Characterize the shared pattern** in one sentence plus the common signal
   (op/function family, error string, root cause). Confirm they truly share a
   root — same code path / identical error — not just a shared report template
   (see `CLAUDE.md` "What counts as a duplicate").

3. **Look for an existing umbrella** before creating one:
   ```
   gh issue list --repo pytorch/pytorch --state open --search "🌂 <keywords> in:title"
   gh issue list --repo pytorch/pytorch --state open --search "umbrella <keywords> in:title"
   ```
   If a fitting umbrella already exists, use it as the keep target.

4. **Otherwise draft a new umbrella and show it first** (title + body + labels)
   per the show-before-acting rule. Title starts with 🌂; body states the shared
   pattern and lists members as a task list:
   ```
   gh issue create --repo pytorch/pytorch \
     --title "🌂 <concise shared pattern>" \
     --label "triaged" [--label "module: ..."] \
     --body "$(cat <<'EOF'
   Umbrella tracking issue for <pattern>.

   Shared root cause: <one paragraph>.

   Members:
   - [ ] #AAAA — <short>
   - [ ] #BBBB — <short>
   EOF
   )"
   ```

5. **Group the members.** Two modes — pick per cluster and say which:
   - **Consolidate** (members are effectively the same bug): close each member as
     a duplicate of the umbrella — `./close_duplicate.py --dup <member> --keep
     <umbrella>`. Port any richer labels from members onto the umbrella first.
   - **Track** (members are the same pattern but each is a distinct actionable
     item): leave members open, and just cross-link — comment on each member
     pointing to the umbrella, and keep the umbrella's checklist as the index.

6. **Record it** in `deduplication.md`: the umbrella number, the members, which
   mode was used, and the shared-root reasoning.

## Notes

- Prefer an existing umbrella over creating a near-duplicate umbrella.
- Creating an issue is outward-facing — show the draft and get confirmation
  before `gh issue create`.
- If members span different modules, add each relevant `module:` label to the
  umbrella so it shows up in the right triage queues.
