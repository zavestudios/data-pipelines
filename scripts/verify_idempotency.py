from __future__ import annotations

import argparse
import json
from datetime import date

from sqlalchemy import create_engine, delete, func, select

from etl.config import EtlConfig
from etl.load.database import ensure_schema, listings_table, write_listings
from etl.sources.csv import read_listings
from etl.transform.normalize import normalize_listings

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify idempotent reruns for listings load")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--run-date", required=True, help="Run date (YYYY-MM-DD)")
    return parser.parse_args(argv)

def count_rows_for_run_date(db_url: str, run_date: str) -> int:
    run_day = date.fromisoformat(run_date)
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.begin() as conn:
        stmt = select(func.count()).select_from(listings_table).where(
              listings_table.c.run_date == run_day
        )
        return int(conn.execute(stmt).scalar_one())

def clear_run_date(db_url: str, run_date: str) -> None:
    run_day = date.fromisoformat(run_date)
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(delete(listings_table).where(listings_table.c.run_date == run_day))

def main() -> None:
    args = parse_args()
    cfg = EtlConfig()
    db_url = cfg.db().sqlalchemy_url()

    ensure_schema(db_url)
    clear_run_date(db_url, args.run_date)

    raw = read_listings(args.input)
    normalized, rejected = normalize_listings(
        raw, source_file=args.input, run_date=args.run_date
    )
    if rejected:
        raise ValueError(f"expected zero rejects for verification input, got {len(rejected)}")

    first = write_listings(normalized, db_url)
    second = write_listings(normalized, db_url)
    final_count = count_rows_for_run_date(db_url, args.run_date)

    expected_rows = len(normalized)
    if first.inserted != expected_rows or first.updated != 0:
            raise ValueError(
                 f"first run mismatch: inserted={first.inserted} updated={first.updated} expected_inserted={expected_rows}"
            )
    if second.inserted != 0 or second.updated != expected_rows:
            raise ValueError(
                 f"second run mismatch: inserted={second.inserted} updated={second.updated} expected_updated={expected_rows}"
            )
    if final_count != expected_rows:
            raise ValueError(
                  f"logical row count mismatch after rerun: got={final_count} expected={expected_rows}"
            )

    print(
          json.dumps(
                {
                      "event": "idempotency_verification_passed",
                      "run_date": args.run_date,
                      "expected_rows": expected_rows,
                      "first_run": first.model_dump(),
                      "second_run": second.model_dump(),
                      "rows_for_run_date": final_count,
                }
          )
    )
        
if __name__ == "__main__":
      main()
