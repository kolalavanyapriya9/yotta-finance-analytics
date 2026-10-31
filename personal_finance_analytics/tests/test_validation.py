from pathlib import Path
import shutil

import pandas as pd

from src.validate import (
    validate_unique,
    validate_fk,
    validate_positive,
    validate_dates,
    validate_transaction_signs,
    validate_dataset,
    validate_outputs,
)


def test_pk_and_fk_helpers():
    assert validate_unique(pd.DataFrame({"id": ["a", "b"]}), "id")
    assert not validate_unique(pd.DataFrame({"id": ["a", "a"]}), "id")

    assert validate_fk(
        pd.DataFrame({"parent": ["a", "b"]}),
        "parent",
        pd.DataFrame({"id": ["a", "b"]}),
        "id",
    )


def test_unique_rejects_null_and_missing_column():
    assert not validate_unique(pd.DataFrame({"id": ["a", None]}), "id")
    assert not validate_unique(pd.DataFrame({"other": ["a"]}), "id")


def test_fk_rejects_invalid_reference_and_null():
    parent = pd.DataFrame({"id": ["a", "b"]})

    assert not validate_fk(
        pd.DataFrame({"parent": ["a", "c"]}), "parent", parent, "id"
    )

    assert not validate_fk(
        pd.DataFrame({"parent": ["a", None]}), "parent", parent, "id"
    )


def test_positive_values():
    assert validate_positive(pd.DataFrame({"amount": [10, 20]}), "amount")
    assert not validate_positive(pd.DataFrame({"amount": [10, 0]}), "amount")
    assert not validate_positive(pd.DataFrame({"amount": [10, -5]}), "amount")


def test_date_validation():
    assert validate_dates(
        pd.DataFrame({"date": ["2026-01-01", "2026-02-01"]}), "date"
    )

    assert not validate_dates(
        pd.DataFrame({"date": ["2026-01-01", "invalid-date"]}), "date"
    )


def test_dataset_validator_detects_duplicate_transaction_id(tmp_path):
    source = Path("data/raw/demo")

    for file in source.glob("*.csv"):
        shutil.copy(file, tmp_path / file.name)

    transactions = pd.read_csv(tmp_path / "transactions.csv")
    transactions.loc[1, "transaction_id"] = transactions.loc[0, "transaction_id"]
    transactions.to_csv(tmp_path / "transactions.csv", index=False)

    checks = validate_dataset(tmp_path)

    assert checks["transactions_pk_unique"] is False


def test_dataset_validator_detects_invalid_account_reference(tmp_path):
    source = Path("data/raw/demo")

    for file in source.glob("*.csv"):
        shutil.copy(file, tmp_path / file.name)

    transactions = pd.read_csv(tmp_path / "transactions.csv")
    transactions.loc[0, "account_id"] = "INVALID-ACCOUNT"
    transactions.to_csv(tmp_path / "transactions.csv", index=False)

    checks = validate_dataset(tmp_path)

    assert checks["transactions_account_fk_valid"] is False


def test_transaction_sign_validation():
    valid = pd.DataFrame({
        "transaction_type": [
            "PURCHASE",
            "REFUND",
            "SALARY",
            "TRANSFER_OUT",
            "TRANSFER_IN",
        ],
        "amount_minor": [-1000, 500, 5000, -2000, 2000],
    })

    assert validate_transaction_signs(valid)


def test_transaction_sign_validation_rejects_wrong_sign():
    invalid = pd.DataFrame({
        "transaction_type": ["PURCHASE", "REFUND"],
        "amount_minor": [1000, -500],
    })

    assert not validate_transaction_signs(invalid)


def test_transaction_sign_validation_rejects_unknown_type():
    invalid = pd.DataFrame({
        "transaction_type": ["UNKNOWN_TRANSACTION"],
        "amount_minor": [1000],
    })

    assert not validate_transaction_signs(invalid)


def test_output_validation_passes_for_demo():
    checks = validate_outputs(
        Path("data/raw/demo"),
        expected_counts={
            "categorized_transactions": 1000,
            "recurring_evaluations": 360,
            "budget_results": 960,
            "insights": 355,
        },
    )

    assert all(checks.values())


def test_output_validation_detects_duplicate_insight_id(tmp_path):
    source = Path("data/raw/demo")

    for file in source.glob("*.csv"):
        shutil.copy(file, tmp_path / file.name)

    insights = pd.read_csv(tmp_path / "insights.csv")
    insights.loc[1, "insight_id"] = insights.loc[0, "insight_id"]
    insights.to_csv(tmp_path / "insights.csv", index=False)

    checks = validate_outputs(tmp_path)

    assert checks["insight_ids_unique"] is False
