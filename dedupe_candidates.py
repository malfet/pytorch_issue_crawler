#!/usr/bin/env python3
"""Surface likely-duplicate GitHub issues from the local SQLite cache.

Adapts the methodology of anthropics/claude-code `.claude/commands/dedupe.md`
to an offline corpus:

  1. "Summarize" each open issue by tokenizing title (weighted) + body.
  2. "Search with diverse keywords" -> a TF-IDF vector space with an inverted
     index so only issues sharing rare terms are ever compared.
  3. "Rank / filter false positives" -> cosine similarity threshold, plus
     dropping bot-generated `DISABLED test_*` tracking issues that look alike
     but each track a distinct test.

Numeric heavy-lifting (per-token outer products of TF-IDF weights) runs on
numpy. No pairwise dense NxN matrix is ever materialized.
"""
from __future__ import annotations

import argparse
import math
import re
import sqlite3
from collections import defaultdict

import numpy as np

TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_.]+")

STOP = set(
    """a an the this that these those is are was were be been being it its it's to of in on
    at for and or but if then else with without from by as into over under we i you he she
    they them our your their my me not no yes do does did doing done have has had can could
    should would may might must will shall get gets got when where why how what which who whom
    while about above below up down out off again further once here there all any both each few
    more most other some such only own same so than too very just also i'm can't don't doesn't
    isn't error issue bug problem using use used like via""".split()
)
# generic in this repo -> little discriminative signal
STOP |= set(
    "pytorch torch python cuda gpu cpu tensor model code test build fail fails failing "
    "support feature request runtime version expected "
    # low-signal PR title words
    "wip poc draft playground fix add update".split()
)

# Auto-generated tracking issues that are near-identical but not real duplicates
# (flaky-test trackers, CI-disable bots, etc.).
BOT_TITLE_PREFIXES = (
    "DISABLED ", "UNSTABLE ", "Test: ", "TestModule:", "Migrate master to main:",
)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 3 and t not in STOP]


def load_issues(con: sqlite3.Connection, slug: str, include_bot: bool, is_pr: bool):
    rows = con.execute(
        "SELECT number, title, COALESCE(body, ''), COALESCE(labels, '[]'), "
        "COALESCE(user, '') "
        "FROM issues WHERE slug = ? AND is_pull_request = ? AND state = 'open'",
        (slug, 1 if is_pr else 0),
    ).fetchall()
    out = []
    for number, title, body, labels, user in rows:
        if not include_bot and title and title.startswith(BOT_TITLE_PREFIXES):
            continue
        # Meta's internal-sync bots mirror human PRs verbatim; skip so they
        # don't show up as "competing" duplicates of the human original.
        if not include_bot and (user.endswith("[bot]") or user == "pytorchbot"):
            continue
        out.append((number, title, body, labels, user))
    return out


def build_vectors(issues, title_weight: float, df_cap: int, min_df: int):
    """Return (vecs, titles, authors, n)."""
    titles = {}
    authors = {}
    bags = {}
    for number, title, body, _labels, user in issues:
        titles[number] = title
        authors[number] = user
        bag: dict[str, float] = defaultdict(float)
        for tok in tokenize(title):
            bag[tok] += title_weight
        for tok in tokenize(body[:2000]):
            bag[tok] += 1.0
        if bag:
            bags[number] = bag

    n = len(bags)
    df: dict[str, int] = defaultdict(int)
    for bag in bags.values():
        for tok in bag:
            df[tok] += 1

    idf = {
        tok: math.log(n / d)
        for tok, d in df.items()
        if min_df <= d <= df_cap
    }

    vecs = {}
    for number, bag in bags.items():
        v = {tok: (1.0 + math.log(cnt)) * idf[tok] for tok, cnt in bag.items() if tok in idf}
        if not v:
            continue
        norm = math.sqrt(sum(w * w for w in v.values()))
        vecs[number] = {tok: w / norm for tok, w in v.items()}
    return vecs, titles, authors, n


def cosine_pairs(vecs, df_cap: int):
    """Accumulate cosine similarity via an inverted index; numpy for the math."""
    inverted: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for number, v in vecs.items():
        for tok, w in v.items():
            inverted[tok].append((number, w))

    sims: dict[tuple[int, int], float] = defaultdict(float)
    for postings in inverted.values():
        m = len(postings)
        if m < 2 or m > df_cap:  # df_cap already applied, but guard anyway
            continue
        nums = [p[0] for p in postings]
        w = np.fromiter((p[1] for p in postings), dtype=np.float64, count=m)
        outer = np.outer(w, w)
        iu, ju = np.triu_indices(m, k=1)
        contrib = outer[iu, ju]
        for a, b, c in zip((nums[i] for i in iu), (nums[j] for j in ju), contrib):
            key = (a, b) if a < b else (b, a)
            sims[key] += c
    return sims


def shared_terms(vecs, a: int, b: int, k: int = 6) -> list[str]:
    va, vb = vecs[a], vecs[b]
    common = sorted(((va[t] * vb[t], t) for t in va if t in vb), reverse=True)
    return [t for _, t in common[:k]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="issues.db")
    ap.add_argument("--slug", default="pytorch/pytorch")
    ap.add_argument("--threshold", type=float, default=0.35, help="min cosine similarity")
    ap.add_argument("--top", type=int, default=40, help="how many pairs to print")
    ap.add_argument("--title-weight", type=float, default=3.0)
    ap.add_argument("--df-cap", type=int, default=60, help="ignore terms in > this many issues")
    ap.add_argument("--min-df", type=int, default=2)
    ap.add_argument("--include-bot", action="store_true",
                    help="include auto-generated DISABLED/UNSTABLE tracking issues")
    ap.add_argument("--prs", action="store_true",
                    help="dedupe open PRs instead of issues (competing implementations)")
    ap.add_argument("--different-authors", action="store_true",
                    help="only report pairs by different authors (default on with --prs)")
    args = ap.parse_args()

    kind = "PRs" if args.prs else "issues"
    diff_authors = args.different_authors or args.prs

    con = sqlite3.connect(args.db)
    issues = load_issues(con, args.slug, args.include_bot, args.prs)
    vecs, titles, authors, n = build_vectors(issues, args.title_weight, args.df_cap, args.min_df)
    sims = cosine_pairs(vecs, args.df_cap)

    pairs = sorted(
        (
            (s, a, b) for (a, b), s in sims.items()
            if s >= args.threshold
            and not (diff_authors and authors.get(a) == authors.get(b))
        ),
        reverse=True,
    )

    print(f"# {args.slug}: {n} open {kind} considered "
          f"({len(issues)} after bot filter), "
          f"{len(pairs)} candidate pairs at cosine >= {args.threshold}"
          f"{' (different authors only)' if diff_authors else ''}\n")
    for s, a, b in pairs[: args.top]:
        print(f"[{s:.2f}] #{a} (@{authors.get(a)})  <->  #{b} (@{authors.get(b)})")
        print(f"        #{a}: {titles[a]}")
        print(f"        #{b}: {titles[b]}")
        print(f"        shared: {', '.join(shared_terms(vecs, a, b))}\n")


if __name__ == "__main__":
    main()
