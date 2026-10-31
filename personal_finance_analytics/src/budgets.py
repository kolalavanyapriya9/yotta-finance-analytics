
"""Compare posted transaction spending against valid monthly budgets."""

import pandas as pd


def compare_budgets(
    transactions: pd.DataFrame,
    budgets: pd.DataFrame,
    accounts: pd.DataFrame
) -> pd.DataFrame:

    tx = transactions.copy()
    b = budgets.copy()
    acc = accounts[["account_id", "user_id"]].copy()

    # Ensure each account maps to only one user.
    if acc["account_id"].duplicated().any():
        raise ValueError("Duplicate account_id found in accounts.")

    # Attach the actual user_id using the account relationship.
    tx = tx.merge(
        acc,
        on="account_id",
        how="left",
        validate="many_to_one"
    )

    if tx["user_id"].isna().any():
        raise ValueError("Some transactions have no matching account.")

    # Use the predicted category when categorization has been performed.
    category_col = (
        "predicted_category_id"
        if "predicted_category_id" in tx.columns
        else "category_id"
    )

    tx["category_id"] = tx[category_col]

    # Only posted transactions should affect budgets.
    if "status" in tx.columns:
        tx = tx[tx["status"] == "POSTED"].copy()

    # Exclude quarantined budgets from all calculations.
    if "status" in b.columns:
        b = b[
            b["status"].astype("string").str.upper() != "QUARANTINED"
        ].copy()

    # Convert transaction dates into monthly periods.
    tx["month"] = (
        pd.to_datetime(
            tx["local_transaction_date"],
            errors="coerce"
        )
        .dt.to_period("M")
        .astype("string")
    )

    tx = tx[tx["month"].notna()].copy()

    # Purchases increase spending; refunds reduce spending.
    tx["net_spend_minor"] = 0

    purchase_mask = tx["transaction_type"] == "PURCHASE"
    refund_mask = tx["transaction_type"] == "REFUND"

    tx.loc[purchase_mask, "net_spend_minor"] = (
        -pd.to_numeric(
            tx.loc[purchase_mask, "amount_minor"],
            errors="coerce"
        )
    )

    tx.loc[refund_mask, "net_spend_minor"] = (
        -pd.to_numeric(
            tx.loc[refund_mask, "amount_minor"],
            errors="coerce"
        )
    )

    # Aggregate spending by user, category and month.
    actuals = (
        tx.groupby(
            ["user_id", "category_id", "month"],
            as_index=False
        )["net_spend_minor"]
        .sum()
    )

    # Convert budget start dates into monthly periods.
    b["month"] = (
        pd.to_datetime(b["period_start"], errors="coerce")
        .dt.to_period("M")
        .astype("string")
    )

    b = b[b["month"].notna()].copy()

    # Attach actual spending to each valid budget.
    out = b.merge(
        actuals,
        on=["user_id", "category_id", "month"],
        how="left",
        validate="many_to_one"
    )

    out["actual_spend_minor"] = (
        out["net_spend_minor"]
        .fillna(0)
        .astype("int64")
    )

    out["variance_minor"] = (
        out["actual_spend_minor"] - out["budget_limit_minor"]
    )

    out["utilization_pct"] = (
        out["actual_spend_minor"]
        .div(
            out["budget_limit_minor"].where(
                out["budget_limit_minor"] != 0
            )
        )
        * 100
    )

    out["budget_status"] = out["variance_minor"].apply(
        lambda value: (
            "OVER_BUDGET" if value > 0 else "WITHIN_BUDGET"
        )
    )

    return out.drop(columns=["net_spend_minor"])
