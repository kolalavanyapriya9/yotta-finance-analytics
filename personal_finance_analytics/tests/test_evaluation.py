
import pandas as pd
import pytest

from src.evaluate import evaluate_recurring_cases


def test_recurring_evaluation_metrics():
    test_cases = pd.DataFrame({
        "recurring_id": ["REC-1", "REC-2"],
        "expected_date": ["2026-02-01", "2026-03-05"],
        "case": ["MISSING", "DELAYED"],
    })

    results = pd.DataFrame({
        "recurring_id": ["REC-1", "REC-2"],
        "expected_date": ["2026-02-01", "2026-03-05"],
        "matched_transaction_count": [0, 1],
        "status": ["POSSIBLE_MISSED", "DELAYED"],
    })

    details, metrics = evaluate_recurring_cases(test_cases, results)

    assert details["correct"].all()
    assert metrics["total_cases"] == 2
    assert metrics["correct_cases"] == 2
    assert metrics["accuracy_pct"] == 100.0


def test_recurring_evaluation_detects_wrong_prediction():
    test_cases = pd.DataFrame({
        "recurring_id": ["REC-1"],
        "expected_date": ["2026-02-01"],
        "case": ["MISSING"],
    })

    results = pd.DataFrame({
        "recurring_id": ["REC-1"],
        "expected_date": ["2026-02-01"],
        "matched_transaction_count": [1],
        "status": ["PAID"],
    })

    details, metrics = evaluate_recurring_cases(test_cases, results)

    assert not details["correct"].iloc[0]
    assert metrics["incorrect_cases"] == 1
    assert metrics["accuracy_pct"] == 0.0


def test_recurring_evaluation_rejects_unknown_case():
    test_cases = pd.DataFrame({
        "recurring_id": ["REC-1"],
        "expected_date": ["2026-02-01"],
        "case": ["UNKNOWN_CASE"],
    })

    results = pd.DataFrame({
        "recurring_id": ["REC-1"],
        "expected_date": ["2026-02-01"],
        "matched_transaction_count": [0],
        "status": ["POSSIBLE_MISSED"],
    })

    with pytest.raises(ValueError):
        evaluate_recurring_cases(test_cases, results)
