import pandas as pd
import pytest

from src.budgets import compare_budgets


def test_purchase_refund_and_pending_transaction():
    transactions = pd.DataFrame([
        {
            "transaction_id": "TX1",
            "account_id": "ACC1",
            "local_transaction_date": "2026-01-05",
            "transaction_type": "PURCHASE",
            "amount_minor": -12000,
            "status": "POSTED",
            "predicted_category_id": "CAT-FOOD",
        },
        {
            "transaction_id": "TX2",
            "account_id": "ACC1",
            "local_transaction_date": "2026-01-10",
            "transaction_type": "REFUND",
            "amount_minor": 2000,
            "status": "POSTED",
            "predicted_category_id": "CAT-FOOD",
        },
        {
            "transaction_id": "TX3",
            "account_id": "ACC1",
            "local_transaction_date": "2026-01-15",
            "transaction_type": "PURCHASE",
            "amount_minor": -5000,
            "status": "PENDING",
            "predicted_category_id": "CAT-FOOD",
        },
    ])

    accounts = pd.DataFrame([
        {"account_id": "ACC1", "user_id": "USR1"}
    ])

    budgets = pd.DataFrame([
        {
            "user_id": "USR1",
            "category_id": "CAT-FOOD",
            "period_start": "2026-01-01",
            "budget_limit_minor": 10000,
        }
    ])

    result = compare_budgets(transactions, budgets, accounts)

    assert result.iloc[0]["actual_spend_minor"] == 10000
    assert result.iloc[0]["variance_minor"] == 0
    assert result.iloc[0]["budget_status"] == "WITHIN_BUDGET"


def test_account_user_mapping():
    transactions = pd.DataFrame([
        {
            "account_id": "ACCOUNT_X",
            "local_transaction_date": "2026-01-05",
            "transaction_type": "PURCHASE",
            "amount_minor": -15000,
            "status": "POSTED",
            "predicted_category_id": "CAT-FOOD",
        }
    ])

    accounts = pd.DataFrame([
        {"account_id": "ACCOUNT_X", "user_id": "REAL_USER"}
    ])

    budgets = pd.DataFrame([
        {
            "user_id": "REAL_USER",
            "category_id": "CAT-FOOD",
            "period_start": "2026-01-01",
            "budget_limit_minor": 10000,
        }
    ])

    result = compare_budgets(transactions, budgets, accounts)

    assert result.iloc[0]["actual_spend_minor"] == 15000
    assert result.iloc[0]["budget_status"] == "OVER_BUDGET"


def test_unmatched_account_raises_error():
    transactions = pd.DataFrame([
        {
            "account_id": "UNKNOWN",
            "local_transaction_date": "2026-01-05",
            "transaction_type": "PURCHASE",
            "amount_minor": -5000,
            "status": "POSTED",
            "predicted_category_id": "CAT-FOOD",
        }
    ])

    accounts = pd.DataFrame([
        {"account_id": "ACC1", "user_id": "USR1"}
    ])

    budgets = pd.DataFrame([
        {
            "user_id": "USR1",
            "category_id": "CAT-FOOD",
            "period_start": "2026-01-01",
            "budget_limit_minor": 10000,
        }
    ])

    with pytest.raises(ValueError):
        compare_budgets(transactions, budgets, accounts)