"""Generate reproducible synthetic household-finance data.

Examples:
  python -m src.generate_data --users 10 --transactions 1000 --out data/raw/demo
  python -m src.generate_data --users 1000 --transactions 500000 --out data/raw/full
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import SEED, START_DATE, END_DATE, CURRENCY


CATEGORIES = [
    ("CAT-INCOME", "Income", "INCOME"),
    ("CAT-FOOD", "Groceries", "EXPENSE"),
    ("CAT-HOUSING", "Housing", "EXPENSE"),
    ("CAT-UTIL", "Utilities", "EXPENSE"),
    ("CAT-TRANSPORT", "Transport", "EXPENSE"),
    ("CAT-SHOP", "Shopping", "EXPENSE"),
    ("CAT-SUB", "Subscriptions", "EXPENSE"),
    ("CAT-HEALTH", "Healthcare", "EXPENSE"),
    ("CAT-TRANSFER", "Transfer", "TRANSFER"),
    ("CAT-REFUND", "Refund", "REFUND"),
    ("CAT-OTHER", "Other", "EXPENSE"),
]

MERCHANTS = [
    ("MER-000001", "FreshMart", "GROCERIES", ["FRESHMART", "FRESH MART", "FM MARKET"]),
    ("MER-000002", "City Rentals", "HOUSING", ["CITY RENT", "CITY RENTALS"]),
    ("MER-000003", "PowerGrid", "UTILITIES", ["POWERGRID", "ELECTRIC BILL"]),
    ("MER-000004", "Metro Transit", "TRANSPORT", ["METRO", "CITY BUS"]),
    ("MER-000005", "StyleHub", "SHOPPING", ["STYLEHUB", "STYLE HUB"]),
    ("MER-000006", "StreamFlix", "SUBSCRIPTIONS", ["STREAMFLIX", "STREAMFLIX.COM"]),
    ("MER-000007", "HealthPlus", "HEALTHCARE", ["HEALTHPLUS", "PHARMACY"]),
    ("MER-000008", "Employer Payroll", "INCOME", ["SALARY CREDIT", "PAYROLL"]),
    ("MER-000009", "Internal Transfer", "TRANSFER", ["OWN ACCOUNT TRANSFER", "SAVINGS TRANSFER"]),
    ("MER-000010", "General Store", "OTHER", ["GENERAL STORE", "MISC PURCHASE"]),
]

RULE_MAP = {
    "GROCERIES": "CAT-FOOD",
    "HOUSING": "CAT-HOUSING",
    "UTILITIES": "CAT-UTIL",
    "TRANSPORT": "CAT-TRANSPORT",
    "SHOPPING": "CAT-SHOP",
    "SUBSCRIPTIONS": "CAT-SUB",
    "HEALTHCARE": "CAT-HEALTH",
    "INCOME": "CAT-INCOME",
    "TRANSFER": "CAT-TRANSFER",
    "OTHER": "CAT-OTHER",
}

TRANSACTION_COLUMNS = [
    "transaction_id",
    "account_id",
    "merchant_id",
    "merchant_descriptor",
    "transaction_ts_utc",
    "local_transaction_date",
    "amount_minor",
    "currency",
    "transaction_type",
    "category_id",
    "status",
    "issue_type",
    "transfer_group_id",
    "original_transaction_id",
]

GROUND_TRUTH_COLUMNS = [
    "case_id",
    "entity_type",
    "entity_id",
    "issue_type",
    "expected_decision",
    "severity",
    "expected_date",
    "related_entity_id",
]


def make_id(prefix: str, n: int, width: int = 6) -> str:
    return f"{prefix}-{n:0{width}d}"


def _transaction_time(local_date, rng, start_hour=8, end_hour=22):
    """Return a UTC timestamp and its matching Asia/Kolkata local date."""
    local_timestamp = (
        pd.Timestamp(local_date)
        + pd.Timedelta(
            hours=int(rng.integers(start_hour, end_hour)),
            minutes=int(rng.integers(0, 60)),
        )
    )
    localized = local_timestamp.tz_localize("Asia/Kolkata")
    utc_timestamp = localized.tz_convert("UTC")
    return utc_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"), local_timestamp.date().isoformat()


def _base_transaction(
    account_id,
    merchant,
    local_date,
    amount_minor,
    transaction_type,
    category_id,
    rng,
):
    utc_timestamp, local_date_text = _transaction_time(local_date, rng)
    return {
        "account_id": account_id,
        "merchant_id": merchant[0],
        "merchant_descriptor": str(rng.choice(merchant[3])),
        "transaction_ts_utc": utc_timestamp,
        "local_transaction_date": local_date_text,
        "amount_minor": int(amount_minor),
        "currency": CURRENCY,
        "transaction_type": transaction_type,
        "category_id": category_id,
        "status": "POSTED",
        "issue_type": "",
        "transfer_group_id": "",
        "original_transaction_id": "",
    }


def generate(users: int, transactions: int, seed: int, out: Path):
    if users < 1 or transactions < 1:
        raise ValueError("users and transactions must be positive")

    rng = np.random.default_rng(seed)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    # Users and accounts. Keep the original one-account-per-user shape for
    # small datasets; the full controlled transfer case needs a second account.
    user_rows = []
    account_rows = []
    for i in range(1, users + 1):
        uid = make_id("USR", i)
        user_rows.append(
            {
                "user_id": uid,
                "household_size": int(rng.integers(1, 6)),
                "city": str(
                    rng.choice(
                        ["Vijayawada", "Hyderabad", "Bengaluru", "Chennai", "Pune"]
                    )
                ),
                "timezone": "Asia/Kolkata",
                "created_date": START_DATE,
                "status": "ACTIVE",
            }
        )
        account_rows.append(
            {
                "account_id": f"ACC-{uid}-01",
                "user_id": uid,
                "account_type": "CURRENT",
                "currency": CURRENCY,
                "opening_balance_minor": int(rng.integers(100000, 1000000)),
                "status": "ACTIVE",
            }
        )

    controlled_cases_enabled = transactions >= 200
    if controlled_cases_enabled:
        first_uid = make_id("USR", 1)
        account_rows.append(
            {
                "account_id": f"ACC-{first_uid}-02",
                "user_id": first_uid,
                "account_type": "SAVINGS",
                "currency": CURRENCY,
                "opening_balance_minor": int(rng.integers(100000, 1000000)),
                "status": "ACTIVE",
            }
        )

    users_df = pd.DataFrame(user_rows)
    accounts_df = pd.DataFrame(account_rows)

    merchants_df = pd.DataFrame(
        [
            {
                "merchant_id": merchant[0],
                "merchant_name": merchant[1],
                "merchant_type": merchant[2],
                "aliases": "|".join(merchant[3]),
            }
            for merchant in MERCHANTS
        ]
    )

    categories_df = pd.DataFrame(
        [
            {
                "category_id": category[0],
                "category_name": category[1],
                "category_type": category[2],
                "active": True,
            }
            for category in CATEGORIES
        ]
    )

    rules_df = pd.DataFrame(
        [
            {
                "rule_id": f"RULE-{i:04d}",
                "merchant_type": merchant[2],
                "category_id": RULE_MAP[merchant[2]],
                "priority": 100 - i,
                "effective_from": START_DATE,
                "effective_to": END_DATE,
                "active": True,
            }
            for i, merchant in enumerate(MERCHANTS, 1)
        ]
    )

    # Monthly budgets. issue_type is always present, including for small data.
    budget_rows = []
    expense_categories = [c for c in CATEGORIES if c[2] == "EXPENSE"]
    for uid in users_df["user_id"]:
        for month in range(1, 13):
            for category in expense_categories:
                budget_rows.append(
                    {
                        "budget_id": (
                            f"BUD-{uid}-2026-{month:02d}-"
                            f"{category[0].replace('CAT-', '')}"
                        ),
                        "user_id": uid,
                        "category_id": category[0],
                        "period_start": f"2026-{month:02d}-01",
                        "budget_limit_minor": int(rng.integers(100000, 250001)),
                        "currency": CURRENCY,
                        "status": "ACTIVE",
                        "issue_type": "",
                    }
                )

    # Add one genuinely invalid budget for the controlled full-demo case.
    invalid_budget_id = None
    if controlled_cases_enabled:
        invalid_budget_id = "BUD-CASE-CATEGORY-MISMATCH"
        budget_rows.append(
            {
                "budget_id": invalid_budget_id,
                "user_id": make_id("USR", 1),
                "category_id": "CAT-INCOME",
                "period_start": "2026-06-01",
                "budget_limit_minor": 150000,
                "currency": CURRENCY,
                "status": "QUARANTINED",
                "issue_type": "BUDGET_CATEGORY_MISMATCH",
            }
        )

    budgets_df = pd.DataFrame(budget_rows)

    # Recurring payment definitions.
    recurring_rows = []
    recurring_id = 1
    for uid in users_df["user_id"]:
        account_id = f"ACC-{uid}-01"
        definitions = [
            ("SALARY", "MER-000008", int(rng.integers(2500000, 7000000)), 1),
            ("RENT", "MER-000002", int(rng.integers(700000, 1800000)), 5),
            ("SUBSCRIPTION", "MER-000006", int(rng.integers(49900, 199900)), 15),
        ]
        for series_type, merchant_id, amount, expected_day in definitions:
            recurring_rows.append(
                {
                    "recurring_id": f"REC-{recurring_id:06d}",
                    "user_id": uid,
                    "account_id": account_id,
                    "merchant_id": merchant_id,
                    "series_type": series_type,
                    "frequency": "MONTHLY",
                    "expected_amount_minor": amount,
                    "expected_day": expected_day,
                    "start_date": START_DATE,
                    "end_date": END_DATE,
                    "status": "ACTIVE",
                }
            )
            recurring_id += 1

    recurring_df = pd.DataFrame(recurring_rows)

    # Generate recurring transactions, preserving four labelled detector cases.
    recurring_tx_rows = []
    recurring_cases = []
    recurring_capacity = transactions - min(10, transactions // 5)
    recurring_series_list = list(recurring_df.itertuples(index=False))

    for series_idx, series in enumerate(recurring_series_list):
        if len(recurring_tx_rows) >= recurring_capacity:
            break

        merchant = next(m for m in MERCHANTS if m[0] == series.merchant_id)
        expected_dates = (
            pd.date_range(series.start_date, series.end_date, freq="MS")
            + pd.to_timedelta(series.expected_day - 1, unit="D")
        )

        for month_idx, expected_date in enumerate(expected_dates, start=1):
            if len(recurring_tx_rows) >= recurring_capacity:
                break

            actual_date = expected_date
            amount = int(series.expected_amount_minor)
            duplicate_count = 1
            case_name = None

            if controlled_cases_enabled:
                if series_idx == 0 and month_idx == 2:
                    case_name = "MISSING"
                    recurring_cases.append(
                        {
                            "recurring_id": series.recurring_id,
                            "expected_date": expected_date.date().isoformat(),
                            "case": case_name,
                        }
                    )
                    continue
                if series_idx == 1 and month_idx == 3:
                    case_name = "DELAYED"
                    actual_date = expected_date + pd.Timedelta(days=4)
                elif series_idx == 2 and month_idx == 4:
                    case_name = "AMOUNT_MISMATCH"
                    amount = int(round(amount * 1.35))
                elif series_idx == 3 and month_idx == 5:
                    case_name = "DUPLICATE"
                    duplicate_count = 2

                if case_name:
                    recurring_cases.append(
                        {
                            "recurring_id": series.recurring_id,
                            "expected_date": expected_date.date().isoformat(),
                            "case": case_name,
                        }
                    )

            duplicate_count = min(
                duplicate_count,
                recurring_capacity - len(recurring_tx_rows),
            )

            for _ in range(duplicate_count):
                utc_timestamp, local_date_text = _transaction_time(
                    actual_date, rng, start_hour=8, end_hour=18
                )
                if series.series_type == "SALARY":
                    transaction_type = "SALARY"
                    signed_amount = amount
                else:
                    transaction_type = "PURCHASE"
                    signed_amount = -amount

                recurring_tx_rows.append(
                    {
                        "account_id": series.account_id,
                        "merchant_id": series.merchant_id,
                        "merchant_descriptor": str(rng.choice(merchant[3])),
                        "transaction_ts_utc": utc_timestamp,
                        "local_transaction_date": local_date_text,
                        "amount_minor": signed_amount,
                        "currency": CURRENCY,
                        "transaction_type": transaction_type,
                        "category_id": RULE_MAP[merchant[2]],
                        "status": "POSTED",
                        "issue_type": "",
                        "transfer_group_id": "",
                        "original_transaction_id": "",
                    }
                )

    # Reserve five rows for real, linked controlled cases in the full demo:
    # transfer-out + transfer-in, original purchase + refund, timezone boundary.
    controlled_tx_rows = []
    if controlled_cases_enabled:
        first_uid = make_id("USR", 1)
        current_account = f"ACC-{first_uid}-01"
        savings_account = f"ACC-{first_uid}-02"
        transfer_merchant = next(m for m in MERCHANTS if m[0] == "MER-000009")
        shopping_merchant = next(m for m in MERCHANTS if m[0] == "MER-000005")
        utility_merchant = next(m for m in MERCHANTS if m[0] == "MER-000003")

        transfer_amount = 125000
        transfer_out = _base_transaction(
            current_account,
            transfer_merchant,
            "2026-04-12",
            -transfer_amount,
            "TRANSFER_OUT",
            "CAT-TRANSFER",
            rng,
        )
        transfer_out["transfer_group_id"] = "TRF-CASE-000001"
        transfer_out["issue_type"] = "TRANSFER_DOUBLE_COUNT"
        transfer_out["_case_role"] = "transfer_out"

        transfer_in = _base_transaction(
            savings_account,
            transfer_merchant,
            "2026-04-12",
            transfer_amount,
            "TRANSFER_IN",
            "CAT-TRANSFER",
            rng,
        )
        transfer_in["transfer_group_id"] = "TRF-CASE-000001"
        transfer_in["_case_role"] = "transfer_in"

        original_purchase = _base_transaction(
            current_account,
            shopping_merchant,
            "2026-05-08",
            -45900,
            "PURCHASE",
            "CAT-SHOP",
            rng,
        )
        original_purchase["_case_role"] = "refund_original"

        refund = _base_transaction(
            current_account,
            shopping_merchant,
            "2026-05-11",
            45900,
            "REFUND",
            "CAT-REFUND",
            rng,
        )
        refund["issue_type"] = "REFUND_AS_NEW_EXPENSE"
        refund["_case_role"] = "refund"

        # 19:30 UTC on Aug 22 is Aug 23 in Asia/Kolkata.
        timezone_case = {
            "account_id": current_account,
            "merchant_id": utility_merchant[0],
            "merchant_descriptor": "POWERGRID",
            "transaction_ts_utc": "2026-08-22T19:30:00Z",
            "local_transaction_date": "2026-08-23",
            "amount_minor": -82500,
            "currency": CURRENCY,
            "transaction_type": "PURCHASE",
            "category_id": "CAT-UTIL",
            "status": "POSTED",
            "issue_type": "TIMEZONE_BOUNDARY",
            "transfer_group_id": "",
            "original_transaction_id": "",
            "_case_role": "timezone",
        }

        controlled_tx_rows = [
            transfer_out,
            transfer_in,
            original_purchase,
            refund,
            timezone_case,
        ]

    # Ordinary transactions fill the exact remaining requested volume.
    # Transfer merchant is deliberately excluded: ordinary one-sided transfer
    # rows are not valid paired-transfer examples.
    ordinary_merchants = [
        merchant
        for merchant in MERCHANTS
        if merchant[2] not in ("INCOME", "HOUSING", "SUBSCRIPTIONS", "TRANSFER")
    ]

    ordinary_count = (
        transactions - len(recurring_tx_rows) - len(controlled_tx_rows)
    )
    if ordinary_count < 0:
        raise ValueError(
            "Not enough transaction capacity for recurring and controlled records."
        )

    ordinary_tx_rows = []
    user_indices = rng.integers(0, users, size=ordinary_count)
    date_indices = rng.integers(0, len(pd.date_range(START_DATE, END_DATE, freq="D")), size=ordinary_count)
    merchant_indices = rng.integers(0, len(ordinary_merchants), size=ordinary_count)
    dates = pd.date_range(START_DATE, END_DATE, freq="D")

    for user_index, date_index, merchant_index in zip(
        user_indices, date_indices, merchant_indices
    ):
        merchant = ordinary_merchants[int(merchant_index)]
        uid = users_df.iloc[int(user_index)]["user_id"]
        merchant_type = merchant[2]
        amount = int(rng.integers(5000, 250000))
        transaction_type = "PURCHASE"
        signed_amount = -amount
        category_id = RULE_MAP[merchant_type]

        if rng.random() < 0.025:
            transaction_type = "REFUND"
            signed_amount = amount
            category_id = "CAT-REFUND"

        ordinary_tx_rows.append(
            _base_transaction(
                f"ACC-{uid}-01",
                merchant,
                dates[int(date_index)],
                signed_amount,
                transaction_type,
                category_id,
                rng,
            )
        )

    # Combine rows, assign stable transaction IDs, then resolve linked IDs.
    tx_rows = recurring_tx_rows + ordinary_tx_rows + controlled_tx_rows
    rng.shuffle(tx_rows)

    for number, row in enumerate(tx_rows, start=1):
        row["transaction_id"] = f"TXN-2026-{number:08d}"

    role_to_id = {
        row["_case_role"]: row["transaction_id"]
        for row in tx_rows
        if "_case_role" in row
    }

    if controlled_cases_enabled:
        refund_row = next(row for row in tx_rows if row.get("_case_role") == "refund")
        refund_row["original_transaction_id"] = role_to_id["refund_original"]

    for row in tx_rows:
        row.pop("_case_role", None)

    tx_df = pd.DataFrame(tx_rows, columns=TRANSACTION_COLUMNS)

    recurring_cases_df = pd.DataFrame(
        recurring_cases,
        columns=["recurring_id", "expected_date", "case"],
    )

    # Ground truth points to the actual entity that contains each anomaly.
    ground_truth_rows = []
    if controlled_cases_enabled:
        cases = [
            {
                "entity_type": "Transaction",
                "entity_id": role_to_id["transfer_out"],
                "issue_type": "TRANSFER_DOUBLE_COUNT",
                "expected_decision": "EXCLUDE_FROM_SPENDING",
                "expected_date": "2026-04-12",
                "related_entity_id": role_to_id["transfer_in"],
            },
            {
                "entity_type": "Transaction",
                "entity_id": role_to_id["refund"],
                "issue_type": "REFUND_AS_NEW_EXPENSE",
                "expected_decision": "OFFSET_ORIGINAL_EXPENSE",
                "expected_date": "2026-05-11",
                "related_entity_id": role_to_id["refund_original"],
            },
            {
                "entity_type": "RecurringSeries",
                "entity_id": "REC-000001",
                "issue_type": "RECURRING_SERIES_SKIP",
                "expected_decision": "FLAG_POSSIBLE_MISSED",
                "expected_date": "2026-02-01",
                "related_entity_id": "",
            },
            {
                "entity_type": "Transaction",
                "entity_id": role_to_id["timezone"],
                "issue_type": "TIMEZONE_BOUNDARY",
                "expected_decision": "DERIVE_LOCAL_DATE_FROM_TIMEZONE",
                "expected_date": "2026-08-23",
                "related_entity_id": "",
            },
            {
                "entity_type": "Budget",
                "entity_id": invalid_budget_id,
                "issue_type": "BUDGET_CATEGORY_MISMATCH",
                "expected_decision": "QUARANTINE_INVALID_BUDGET",
                "expected_date": "2026-06-01",
                "related_entity_id": "",
            },
        ]

        for index, case in enumerate(cases, start=1):
            ground_truth_rows.append(
                {
                    "case_id": f"CASE-{index:06d}",
                    "severity": "MEDIUM",
                    **case,
                }
            )

    ground_truth_df = pd.DataFrame(
        ground_truth_rows,
        columns=GROUND_TRUTH_COLUMNS,
    )

    tables = {
        "users": users_df,
        "accounts": accounts_df,
        "merchants": merchants_df,
        "categories": categories_df,
        "category_rules": rules_df,
        "budgets": budgets_df,
        "recurring_series": recurring_df,
        "transactions": tx_df,
        "recurring_test_cases": recurring_cases_df,
    }

    for name, dataframe in tables.items():
        dataframe.to_csv(out / f"{name}.csv", index=False)

    ground_truth_dir = out.parent / "ground_truth"
    ground_truth_dir.mkdir(parents=True, exist_ok=True)
    ground_truth_df.to_csv(
        ground_truth_dir / "ground_truth.csv",
        index=False,
    )

    manifest = {
        "seed": seed,
        "users": users,
        "transactions": transactions,
        "months": 12,
        "currency": CURRENCY,
        "generator": "src.generate_data",
        "synthetic": True,
    }
    (out / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {name: len(dataframe) for name, dataframe in tables.items()},
            indent=2,
        )
    )
    print(f"Output: {out.resolve()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--transactions", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, default=Path("data/raw/demo"))
    args = parser.parse_args()
    generate(args.users, args.transactions, args.seed, args.out)


if __name__ == "__main__":
    main()
