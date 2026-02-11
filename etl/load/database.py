from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, MetaData, Numeric, String, Table, Column, TIMESTAMP, create_engine, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from etl.models import LoadResult, NormalizedListing


metadata = MetaData()
listings_table = Table(
    "listings",
    metadata,
    Column("address", String, primary_key=True),
    Column("run_date", Date, primary_key=True),
    Column("price", Numeric(12, 2), nullable=False),
    Column("source_file", String, nullable=False),
    Column("loaded_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
)


def ensure_schema(db_url: str) -> None:
    engine = create_engine(db_url, pool_pre_ping=True)
    metadata.create_all(engine)


def write_listings(records: list[NormalizedListing], db_url: str) -> LoadResult:
    if not records:
        return LoadResult(inserted=0, updated=0, rejected=0, processed=0)

    payload = [
        {
            "address": r.address,
            "price": r.price,
            "source_file": r.source_file,
            "run_date": date.fromisoformat(r.run_date),
            "loaded_at": datetime.utcnow(),
        }
        for r in records
    ]
    keys = [(row["address"], row["run_date"]) for row in payload]

    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.begin() as conn:
        existing_stmt = select(func.count()).select_from(listings_table).where(
            tuple_(listings_table.c.address, listings_table.c.run_date).in_(keys)
        )
        existing = int(conn.execute(existing_stmt).scalar_one())
        stmt = insert(listings_table).values(payload)
        upsert = stmt.on_conflict_do_update(
            index_elements=[listings_table.c.address, listings_table.c.run_date],
            set_={
                "price": stmt.excluded.price,
                "source_file": stmt.excluded.source_file,
                "loaded_at": stmt.excluded.loaded_at,
            },
        )
        result = conn.execute(upsert)

    affected = result.rowcount or 0
    inserted = max(0, len(records) - existing)
    updated = max(0, affected - inserted)
    return LoadResult(inserted=inserted, updated=updated, rejected=0, processed=len(records))


def assert_rows_for_run_date(db_url: str, run_date: str) -> int:
    run_day = date.fromisoformat(run_date)
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.begin() as conn:
        stmt = select(func.count()).select_from(listings_table).where(listings_table.c.run_date == run_day)
        rows = conn.execute(stmt).scalar_one()
    if rows <= 0:
        raise ValueError(f"no rows loaded for run_date={run_date}")
    return int(rows)
