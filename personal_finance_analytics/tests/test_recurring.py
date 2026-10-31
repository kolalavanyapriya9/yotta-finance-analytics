
import pandas as pd
import pytest

from src.recurring import evaluate_recurring


@pytest.mark.parametrize(
    "case, start, end, day, transactions, target_date, expected_status",
    [
        (
            "MISSING",
            "2026-01-01",
            "2026-03-31",
            5,
            ["2026-01-05", "2026-03-05"],
            "2026-02-05",
            "POSSIBLE_MISSED",
        ),
        (
            "DELAYED",
            "2026-03-01",
            "2026-03-31",
            5,
            ["2026-03-09"],
            "2026-03-05",
            "DELAYED",
        ),
        (
            "AMOUNT_MISMATCH",
            "2026-04-01",
            "2026-04-30",
            15,
            ["2026-04-15"],
            "2026-04-15",
            "AMOUNT_MISMATCH",
        ),
        (
            "DUPLICATE",
            "2026-05-01",
            "2026-05-31",
            1,
            ["2026-05-01", "2026-05-01"],
            "2026-05-01",
            "DUPLICATE",
        ),
    ],
)
def test_recurring_exception_detection(
    case, start, end, day, transactions, target_date, expected_status
):
    series = pd.DataFrame([{
        "recurring_id": "REC-TEST",
        "user_id": "USR-TEST",
        "account_id": "ACC-TEST",
        "merchant_id": "MER-TEST",
        "series_type": "SUBSCRIPTION",
        "frequency": "MONTHLY",
        "expected_amount_minor": 10000,
        "expected_day": day,
        "start_date": start,
        "end_date": end,
        "status": "ACTIVE",
    }])

    amounts = {
        "AMOUNT_MISMATCH": 12000,
    }

    tx_rows = []

    for i, date in enumerate(transactions):
        tx_rows.append({
            "transaction_id": f"TXN-{i}",
            "account_id": "ACC-TEST",
            "merchant_id": "MER-TEST",
            "local_transaction_date": date,
            "amount_minor": -amounts.get(case, 10000),
            "transaction_type": "PURCHASE",
            "status": "POSTED",
        })

    tx = pd.DataFrame(tx_rows)

    result = evaluate_recurring(tx, series)

    actual = result[result["expected_date"] == target_date]

    assert len(actual) == 1
    assert actual.iloc[0]["status"] == expected_status
