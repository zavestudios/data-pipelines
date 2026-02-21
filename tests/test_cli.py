import pytest

from etl.jobs.ingest_csv import parse_args

def test_parse_args_accepts_iso_run_date() -> None:
    args = parse_args(
        ["--input", "data/listing.csv", "--run-date", "2026-02-11", "--stage", "extract_validate"]
    )
    assert args.run_date == "2026-02-11"
    assert args.stage == "extract_validate"

def test_parse_args_rejects_non_date_run_date() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--input", "data/listings.csv", "--run-date", "2026-02-11T01:02:03"])

def test_parse_args_rejects_bad_format_run_date() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--input", "data/listings.csv", "--run-date", "02/11/2026"])