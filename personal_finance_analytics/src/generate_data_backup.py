"""Generate reproducible synthetic household-finance data.

Example:
  python -m src.generate_data --users 10 --transactions 1000 --out data/raw/demo
  python -m src.generate_data --users 1000 --transactions 500000 --out data/raw/full
"""
from __future__ import annotations
import argparse, json
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
    "GROCERIES":"CAT-FOOD", "HOUSING":"CAT-HOUSING", "UTILITIES":"CAT-UTIL",
    "TRANSPORT":"CAT-TRANSPORT", "SHOPPING":"CAT-SHOP", "SUBSCRIPTIONS":"CAT-SUB",
    "HEALTHCARE":"CAT-HEALTH", "INCOME":"CAT-INCOME", "TRANSFER":"CAT-TRANSFER",
    "OTHER":"CAT-OTHER"
}

def make_id(prefix, n, width=6):
    return f"{prefix}-{n:0{width}d}"

def generate(users: int, transactions: int, seed: int, out: Path):
    if users < 1 or transactions < 1:
        raise ValueError("users and transactions must be positive")
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    user_rows, account_rows = [], []
    for i in range(1, users + 1):
        uid = make_id("USR", i)
        user_rows.append({"user_id":uid, "household_size":int(rng.integers(1,6)),
                          "city":str(rng.choice(["Vijayawada","Hyderabad","Bengaluru","Chennai","Pune"])),
                          "timezone":"Asia/Kolkata", "created_date":START_DATE, "status":"ACTIVE"})
        account_rows.append({"account_id":f"ACC-{uid}-01", "user_id":uid, "account_type":"CURRENT",
                             "currency":CURRENCY, "opening_balance_minor":int(rng.integers(100000,1000000)),
                             "status":"ACTIVE"})
    users_df = pd.DataFrame(user_rows)
    accounts_df = pd.DataFrame(account_rows)
    merchant_rows = [{"merchant_id":m[0],"merchant_name":m[1],"merchant_type":m[2],
                      "aliases":"|".join(m[3])} for m in MERCHANTS]
    merchants_df = pd.DataFrame(merchant_rows)
    categories_df = pd.DataFrame([{"category_id":x[0],"category_name":x[1],"category_type":x[2],"active":True} for x in CATEGORIES])
    rules_df = pd.DataFrame([{"rule_id":f"RULE-{i:04d}","merchant_type":m[2],
                              "category_id":RULE_MAP[m[2]],"priority":100-i,
                              "effective_from":START_DATE,"effective_to":END_DATE,"active":True}
                             for i,m in enumerate(MERCHANTS,1)])
    # Budgets: one per user/month/category for expense categories.
    budget_rows=[]
    expense_cats=[c for c in CATEGORIES if c[2]=="EXPENSE"]
    for u in users_df.user_id:
        for month in range(1,13):
            for cat in expense_cats:
                budget_rows.append({"budget_id":f"BUD-{u}-2026-{month:02d}-{cat[0].replace('CAT-','')}",
                    "user_id":u,"category_id":cat[0],"period_start":f"2026-{month:02d}-01",
                    "budget_limit_minor":int(rng.integers(100000,250001)),"currency":CURRENCY,"status":"ACTIVE"})
    budgets_df=pd.DataFrame(budget_rows)
        # Create recurring payment definitions for each user.
    rec_rows = []
    rec_id = 1

    for u in users_df.user_id:
        acc = f"ACC-{u}-01"

        recurring_definitions = [
            ("SALARY", "MER-000008", int(rng.integers(2500000, 7000000)), 1),
            ("RENT", "MER-000002", int(rng.integers(700000, 1800000)), 5),
            ("SUBSCRIPTION", "MER-000006", int(rng.integers(49900, 199900)), 15)
        ]

        for kind, mid, amount, day in recurring_definitions:
            rec_rows.append({
                "recurring_id": f"REC-{rec_id:06d}",
                "user_id": u,
                "account_id": acc,
                "merchant_id": mid,
                "series_type": kind,
                "frequency": "MONTHLY",
                "expected_amount_minor": amount,
                "expected_day": day,
                "start_date": START_DATE,
                "end_date": END_DATE,
                "status": "ACTIVE"
            })

            rec_id += 1

    recurring_df = pd.DataFrame(rec_rows)
    # Generate recurring transactions within the requested transaction capacity.
    recurring_tx_rows = []
    recurring_cases = []

    recurring_series_list = list(recurring_df.itertuples(index=False))
    dates = pd.date_range(START_DATE, END_DATE, freq="D")

    # Keep some capacity for ordinary transactions. Small test datasets can
    # therefore be generated without requiring every recurring payment.
    ordinary_reserve = min(10, transactions // 5)
    recurring_capacity = transactions - ordinary_reserve

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

            # Introduce known recurring-payment exceptions only in datasets
            # large enough to contain the complete recurring test fixture.
            if transactions >= 200:
                if series_idx == 0 and month_idx == 2:
                    case_name = "MISSING"
                    recurring_cases.append({
                        "recurring_id": series.recurring_id,
                        "expected_date": expected_date.date().isoformat(),
                        "case": case_name
                    })
                    continue
                elif series_idx == 1 and month_idx == 3:
                    actual_date = expected_date + pd.Timedelta(days=4)
                    case_name = "DELAYED"
                elif series_idx == 2 and month_idx == 4:
                    amount = int(round(amount * 1.35))
                    case_name = "AMOUNT_MISMATCH"
                elif series_idx == 3 and month_idx == 5:
                    duplicate_count = 2
                    case_name = "DUPLICATE"

                if case_name:
                    recurring_cases.append({
                        "recurring_id": series.recurring_id,
                        "expected_date": expected_date.date().isoformat(),
                        "case": case_name
                    })

            # Do not allow a duplicate fixture to exceed the requested count.
            duplicate_count = min(
                duplicate_count,
                recurring_capacity - len(recurring_tx_rows)
            )

            for _ in range(duplicate_count):
                timestamp = (
                    pd.Timestamp(actual_date)
                    + pd.Timedelta(
                        hours=int(rng.integers(8, 18)),
                        minutes=int(rng.integers(0, 60))
                    )
                )

                if series.series_type == "SALARY":
                    txn_type = "SALARY"
                    signed_amount = amount
                else:
                    txn_type = "PURCHASE"
                    signed_amount = -amount

                recurring_tx_rows.append({
                    "account_id": series.account_id,
                    "merchant_id": series.merchant_id,
                    "merchant_descriptor": str(rng.choice(merchant[3])),
                    "transaction_ts_utc": timestamp.isoformat() + "Z",
                    "local_transaction_date": timestamp.date().isoformat(),
                    "amount_minor": signed_amount,
                    "currency": CURRENCY,
                    "transaction_type": txn_type,
                    "category_id": RULE_MAP[merchant[2]],
                    "status": "POSTED",
                    "issue_type": ""
                })

    # Add ordinary transactions to fill the remaining requested volume.
    remaining_count = transactions - len(recurring_tx_rows)

    ordinary_merchants = [
        m for m in MERCHANTS
        if m[2] not in ("INCOME", "HOUSING", "SUBSCRIPTIONS")
    ]

    ordinary_tx_rows = []
    user_idx = rng.integers(0, users, size=remaining_count)
    date_idx = rng.integers(0, len(dates), size=remaining_count)
    merchant_idx = rng.integers(0, len(ordinary_merchants), size=remaining_count)

    for ui, di, mi in zip(user_idx, date_idx, merchant_idx):
        merchant = ordinary_merchants[int(mi)]
        uid = users_df.iloc[int(ui)].user_id
        typ = merchant[2]

        if typ == "TRANSFER":
            amount = int(rng.integers(10000, 500000))
            signed = -amount
            txn_type = "TRANSFER_OUT"
        else:
            amount = int(rng.integers(5000, 250000))
            signed = -amount
            txn_type = "PURCHASE"

        if typ != "TRANSFER" and rng.random() < 0.025:
            signed = abs(signed)
            txn_type = "REFUND"

        timestamp = (
            pd.Timestamp(dates[int(di)])
            + pd.Timedelta(
                hours=int(rng.integers(0, 24)),
                minutes=int(rng.integers(0, 60))
            )
        )

        ordinary_tx_rows.append({
            "account_id": f"ACC-{uid}-01",
            "merchant_id": merchant[0],
            "merchant_descriptor": str(rng.choice(merchant[3])),
            "transaction_ts_utc": timestamp.isoformat() + "Z",
            "local_transaction_date": timestamp.date().isoformat(),
            "amount_minor": signed,
            "currency": CURRENCY,
            "transaction_type": txn_type,
            "category_id": (
                "CAT-REFUND" if txn_type == "REFUND"
                else RULE_MAP[typ]
            ),
            "status": "POSTED",
            "issue_type": ""
        })

    # Combine both transaction groups and assign unique transaction IDs.
    tx_rows = recurring_tx_rows + ordinary_tx_rows
    rng.shuffle(tx_rows)

    for n, row in enumerate(tx_rows, start=1):
        row["transaction_id"] = f"TXN-2026-{n:08d}"

    tx_df = pd.DataFrame(tx_rows)
    recurring_cases_df = pd.DataFrame(
        recurring_cases,
        columns=["recurring_id", "expected_date", "case"]
    )

    # Labelled anomaly cases are added as metadata on selected otherwise valid rows.
    ground = []

    if len(tx_df) >= 5:
        cases = [
            ("TRANSFER_DOUBLE_COUNT", 0, "EXCLUDE_FROM_SPENDING"),
            ("REFUND_AS_NEW_EXPENSE", 1, "OFFSET_ORIGINAL_EXPENSE"),
            ("RECURRING_SERIES_SKIP", 2, "FLAG_POSSIBLE_MISSED"),
            ("TIMEZONE_BOUNDARY", 3, "DERIVE_LOCAL_DATE_FROM_TIMEZONE"),
            ("BUDGET_CATEGORY_MISMATCH", 4, "QUARANTINE_INVALID_BUDGET"),
        ]

        for issue, idx, expected in cases:
            tx_df.loc[idx, "issue_type"] = issue

            ground.append({
                "case_id": f"CASE-{len(ground)+1:06d}",
                "entity_type": "Transaction",
                "entity_id": tx_df.loc[idx, "transaction_id"],
                "issue_type": issue,
                "expected_decision": expected,
                "severity": "MEDIUM"
            })

    # Keep recurring test cases and all generated tables.
    tables = {
        "users": users_df,
        "accounts": accounts_df,
        "merchants": merchants_df,
        "categories": categories_df,
        "category_rules": rules_df,
        "budgets": budgets_df,
        "recurring_series": recurring_df,
        "transactions": tx_df,
        "recurring_test_cases": recurring_cases_df
    }
    for name,df in tables.items():
        df.to_csv(out/f"{name}.csv",index=False)
    gt_dir = out.parent/"ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ground).to_csv(gt_dir/"ground_truth.csv",index=False)
    manifest={"seed":seed,"users":users,"transactions":transactions,"months":12,
              "currency":CURRENCY,"generator":"src.generate_data","synthetic":True}
    (out/"source_manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps({k:len(v) for k,v in tables.items()},indent=2))
    print(f"Output: {out.resolve()}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--users",type=int,default=10)
    p.add_argument("--transactions",type=int,default=1000)
    p.add_argument("--seed",type=int,default=SEED)
    p.add_argument("--out",type=Path,default=Path("data/raw/demo"))
    a=p.parse_args()
    generate(a.users,a.transactions,a.seed,a.out)
if __name__=="__main__": main()
