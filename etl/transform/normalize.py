from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable

from etl.models import NormalizedListing, RawListing, RejectedRecord


def normalize_listings(
    records: Iterable[dict], *, source_file: str, run_date: str
) -> tuple[list[NormalizedListing], list[RejectedRecord]]:
    normalized: list[NormalizedListing] = []
    rejected: list[RejectedRecord] = []

    for record in records:
        raw = RawListing(**record, source_file=source_file)
        address = (raw.address or "").strip()
        if not address:
            rejected.append(RejectedRecord(record=record, reason="missing_address"))
            continue

        try:
            parsed_price = Decimal((raw.price or "0").strip())
        except InvalidOperation:
            rejected.append(RejectedRecord(record=record, reason="invalid_price"))
            continue

        if parsed_price < 0:
            rejected.append(RejectedRecord(record=record, reason="negative_price"))
            continue

        normalized.append(
            NormalizedListing(
                address=address,
                price=parsed_price,
                source_file=source_file,
                run_date=run_date,
            )
        )

    return normalized, rejected
