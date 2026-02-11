from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime

from etl.config import EtlConfig
from etl.load.database import assert_rows_for_run_date, ensure_schema, write_listings
from etl.logging import setup_logging
from etl.sources.csv import read_listings
from etl.transform.normalize import normalize_listings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run listings CSV ETL pipeline")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--run-date", default=date.today().isoformat(), help="Run date (YYYY-MM-DD)")
    parser.add_argument("--batch-id", default="", help="Pipeline batch identifier")
    parser.add_argument(
        "--stage",
        default="load_postgres",
        choices=["extract_validate", "load_postgres", "dq_assertions"],
        help="Execution stage for orchestration",
    )
    return parser.parse_args()


def write_rejects(path: str, rejected: list) -> None:
    if not rejected:
        return
    with open(path, "w", encoding="utf-8") as handle:
        for record in rejected:
            handle.write(
                json.dumps({"reason": record.reason, "record": record.record}, default=str) + "\n"
            )


def main() -> None:
    args = parse_args()
    config = EtlConfig()
    setup_logging(config.etl_log_level)
    logger = logging.getLogger("etl.jobs.ingest_csv")

    datetime.fromisoformat(args.run_date)

    raw = read_listings(args.input)
    normalized, rejected = normalize_listings(raw, source_file=args.input, run_date=args.run_date)
    write_rejects(config.etl_rejects_path, rejected)

    context = {
        "event": "pipeline_stage_started",
        "context": {
            "stage": args.stage,
            "batch_id": args.batch_id,
            "run_date": args.run_date,
            "input_path": args.input,
            "processed_rows": len(raw),
            "normalized_rows": len(normalized),
            "rejected_rows": len(rejected),
        },
    }
    logger.info("stage started", extra=context)

    db_url = config.db().sqlalchemy_url()
    if args.stage == "extract_validate":
        logger.info("extract/validate stage complete", extra={"event": "extract_validate_complete", "context": context["context"]})
        return

    if args.stage == "load_postgres":
        ensure_schema(db_url)
        result = write_listings(normalized, db_url)
        logger.info(
            "load stage complete",
            extra={
                "event": "load_postgres_complete",
                "context": {
                    **context["context"],
                    "db_processed": result.processed,
                    "db_upserted": result.updated,
                },
            },
        )
        return

    if args.stage == "dq_assertions":
        rows = assert_rows_for_run_date(db_url, args.run_date)
        logger.info(
            "dq assertions complete",
            extra={
                "event": "dq_assertions_complete",
                "context": {**context["context"], "rows_for_run_date": rows},
            },
        )
        return


if __name__ == "__main__":
    main()
