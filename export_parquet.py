#!/usr/bin/env python3
"""Export the SQLite issue DB to a Parquet file for publishing.

Parquet is columnar and compresses well (~zstd levels), and is directly
queryable by pandas / DuckDB / Hugging Face without SQLite. Labels are
written as a real list<string> column rather than JSON text.

    ./export_parquet.py                      # issues.db -> issues.parquet
    ./export_parquet.py --db x.db --out y.parquet
"""
import argparse
import json
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq

import fetch_issue as fi

# Column name -> pyarrow type. Order defines the Parquet schema.
_SCHEMA = pa.schema([
    ("slug", pa.string()),
    ("number", pa.int64()),
    ("title", pa.string()),
    ("user", pa.string()),
    ("user_id", pa.int64()),
    ("state", pa.string()),
    ("state_reason", pa.string()),
    ("labels", pa.list_(pa.string())),
    ("body", pa.string()),
    ("is_pull_request", pa.bool_()),
    ("comments", pa.int64()),
    ("created_at", pa.string()),
    ("updated_at", pa.string()),
    ("closed_at", pa.string()),
    ("fetched_at", pa.string()),
])


def export(db_path: str, out_path: str) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM issues ORDER BY number").fetchall()

    columns = {name: [] for name in _SCHEMA.names}
    for row in rows:
        d = dict(row)
        columns["labels"].append(json.loads(d["labels"]) if d["labels"] else [])
        columns["is_pull_request"].append(bool(d["is_pull_request"]))
        for name in _SCHEMA.names:
            if name in ("labels", "is_pull_request"):
                continue
            columns[name].append(d.get(name))

    table = pa.table(
        {name: pa.array(columns[name], type=_SCHEMA.field(name).type)
         for name in _SCHEMA.names},
        schema=_SCHEMA,
    )
    pq.write_table(table, out_path, compression="zstd")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=fi.DEFAULT_DB, help=f"SQLite DB (default: {fi.DEFAULT_DB})")
    parser.add_argument("--out", default="issues.parquet", help="output Parquet path")
    args = parser.parse_args()

    n = export(args.db, args.out)
    print(f"Wrote {n} rows to {args.out}")


if __name__ == "__main__":
    main()
