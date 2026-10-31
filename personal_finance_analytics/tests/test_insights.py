import pandas as pd

from src.insights import build_insights


def test_insight_severity_levels():
    budget_results = pd.DataFrame([
        {
            "user_id": "U1",
            "category_id": "CAT1",
            "month": "2026-01",
            "budget_status": "OVER_BUDGET",
            "actual_spend_minor": 10500,
            "budget_limit_minor": 10000,
            "variance_minor": 500,
        },
        {
            "user_id": "U2",
            "category_id": "CAT2",
            "month": "2026-01",
            "budget_status": "OVER_BUDGET",
            "actual_spend_minor": 12000,
            "budget_limit_minor": 10000,
            "variance_minor": 2000,
        },
        {
            "user_id": "U3",
            "category_id": "CAT3",
            "month": "2026-01",
            "budget_status": "OVER_BUDGET",
            "actual_spend_minor": 14000,
            "budget_limit_minor": 10000,
            "variance_minor": 4000,
        },
    ])

    result = build_insights(budget_results)

    assert result["severity"].tolist() == [
        "LOW", "MEDIUM", "HIGH"
    ]


def test_no_over_budget_records():
    budget_results = pd.DataFrame([
        {
            "user_id": "U1",
            "category_id": "CAT1",
            "month": "2026-01",
            "budget_status": "WITHIN_BUDGET",
            "actual_spend_minor": 8000,
            "budget_limit_minor": 10000,
            "variance_minor": -2000,
        }
    ])

    result = build_insights(budget_results)

    assert result.empty
    assert "severity" in result.columns