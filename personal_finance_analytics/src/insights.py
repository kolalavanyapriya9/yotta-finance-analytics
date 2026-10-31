"""Create severity-based insights from budget outcomes."""

import pandas as pd


OUTPUT_COLUMNS = [
    "insight_id",
    "user_id",
    "category_id",
    "period",
    "insight_type",
    "actual_spend_minor",
    "budget_limit_minor",
    "severity",
]


def build_insights(budget_results: pd.DataFrame) -> pd.DataFrame:

    over = budget_results[
        budget_results["budget_status"] == "OVER_BUDGET"
    ].copy()

    if over.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    over = over.reset_index(drop=True)

    over["insight_id"] = [
        f"INS-{i:08d}" for i in range(1, len(over) + 1)
    ]

    over["period"] = over["month"]
    over["insight_type"] = "BUDGET_EXCEEDED"

    # Calculate the percentage by which spending exceeded the budget.
    over["overage_pct"] = (
        over["variance_minor"]
        .div(over["budget_limit_minor"].where(
            over["budget_limit_minor"] > 0
        ))
        * 100
    )

    # A zero or negative budget with positive overspending
    # is treated as HIGH severity.
    over["severity"] = "HIGH"

    over.loc[
        over["overage_pct"] <= 25,
        "severity"
    ] = "MEDIUM"

    over.loc[
        over["overage_pct"] <= 10,
        "severity"
    ] = "LOW"

    return over[OUTPUT_COLUMNS]