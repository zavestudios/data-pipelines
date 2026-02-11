from etl.transform.normalize import normalize_listings


def test_normalize_listings_accepts_valid_and_rejects_invalid() -> None:
    records = [
        {"address": " 123 Main St ", "price": "100.50"},
        {"address": "", "price": "55"},
        {"address": "9 Broadway", "price": "-1"},
        {"address": "6 Pine", "price": "not-a-number"},
    ]

    normalized, rejected = normalize_listings(records, source_file="input.csv", run_date="2026-02-11")

    assert len(normalized) == 1
    assert normalized[0].address == "123 Main St"
    assert str(normalized[0].price) == "100.50"
    assert len(rejected) == 3
    assert {r.reason for r in rejected} == {"missing_address", "negative_price", "invalid_price"}
