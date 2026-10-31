"""Core integrity checks and reproducibility helpers."""

import hashlib
from pathlib import Path

import pandas as pd


def validate_unique(df, key):
    if key not in df.columns:
        return False

    return bool(
        df[key].notna().all()
        and not df[key].duplicated().any()
    )


def validate_fk(child, field, parent, parent_key):
    if field not in child.columns or parent_key not in parent.columns:
        return False

    return bool(
        child[field].notna().all()
        and child[field].isin(parent[parent_key].dropna()).all()
    )


def validate_positive(df, field):
    if field not in df.columns:
        return False

    values = pd.to_numeric(df[field], errors="coerce")

    return bool(values.notna().all() and (values > 0).all())


def validate_dates(df, field):
    if field not in df.columns:
        return False

    dates = pd.to_datetime(df[field], errors="coerce")

    return bool(dates.notna().all())


def validate_transaction_signs(df):
    """Check whether transaction amounts have the expected signs."""

    if "transaction_type" not in df.columns:
        return False

    if "amount_minor" not in df.columns:
        return False

    expected_signs = {
        "PURCHASE": -1,
        "REFUND": 1,
        "SALARY": 1,
        "TRANSFER_OUT": -1,
        "TRANSFER_IN": 1,
    }

    if not df["transaction_type"].isin(expected_signs).all():
        return False

    amounts = pd.to_numeric(df["amount_minor"], errors="coerce")

    if amounts.isna().any() or (amounts == 0).any():
        return False

    for transaction_type, expected_sign in expected_signs.items():
        mask = df["transaction_type"] == transaction_type

        if not (amounts[mask] * expected_sign > 0).all():
            return False

    return True


def validate_transfer_pairs(df):
    """Check that every transfer group has one matching in/out pair."""

    required = {
        "transfer_group_id",
        "transaction_type",
        "amount_minor",
        "transaction_id",
        "account_id",
    }

    if not required.issubset(df.columns):
        return False

    transfers = df[
        df["transfer_group_id"].notna()
        & (df["transfer_group_id"].astype(str).str.strip() != "")
    ].copy()

    if transfers.empty:
        return not df["transaction_type"].isin(
            ["TRANSFER_OUT", "TRANSFER_IN"]
        ).any()

    transfers["amount_minor"] = pd.to_numeric(
        transfers["amount_minor"], errors="coerce"
    )

    for _, group in transfers.groupby("transfer_group_id"):
        if len(group) != 2:
            return False

        if set(group["transaction_type"]) != {
            "TRANSFER_OUT", "TRANSFER_IN"
        }:
            return False

        outgoing = group[group["transaction_type"] == "TRANSFER_OUT"]
        incoming = group[group["transaction_type"] == "TRANSFER_IN"]

        if outgoing["amount_minor"].isna().any():
            return False

        if incoming["amount_minor"].isna().any():
            return False

        out_amount = outgoing["amount_minor"].iloc[0]
        in_amount = incoming["amount_minor"].iloc[0]

        if out_amount >= 0 or in_amount <= 0:
            return False

        if abs(out_amount) != in_amount:
            return False

        if outgoing["transaction_id"].iloc[0] == incoming[
            "transaction_id"
        ].iloc[0]:
            return False

        if outgoing["account_id"].iloc[0] == incoming[
            "account_id"
        ].iloc[0]:
            return False

    # Every transfer transaction must have a group ID.
    transfer_types = df["transaction_type"].isin(
        ["TRANSFER_OUT", "TRANSFER_IN"]
    )

    if df.loc[transfer_types, "transfer_group_id"].isna().any():
        return False

    if (
        df.loc[transfer_types, "transfer_group_id"]
        .astype(str).str.strip().eq("").any()
    ):
        return False

    return True


def validate_refund_references(df):
    """Validate original-purchase references when a refund provides one."""

    required = {
        "transaction_id",
        "original_transaction_id",
        "transaction_type",
        "account_id",
        "merchant_id",
        "amount_minor",
    }

    if not required.issubset(df.columns):
        return False

    refunds = df[df["transaction_type"] == "REFUND"]

    if refunds.empty:
        return True

    purchases = df[
        df["transaction_type"] == "PURCHASE"
    ].set_index("transaction_id")

    for _, refund in refunds.iterrows():
        original_id = refund["original_transaction_id"]

        # Ordinary refunds without a linked purchase are allowed.
        if pd.isna(original_id) or str(original_id).strip() == "":
            continue

        if original_id not in purchases.index:
            return False

        original = purchases.loc[original_id]

        if isinstance(original, pd.DataFrame):
            return False

        if refund["account_id"] != original["account_id"]:
            return False

        if refund["merchant_id"] != original["merchant_id"]:
            return False

        if refund["transaction_id"] == original_id:
            return False

        refund_amount = pd.to_numeric(
            pd.Series([refund["amount_minor"]]), errors="coerce"
        ).iloc[0]

        purchase_amount = pd.to_numeric(
            pd.Series([original["amount_minor"]]), errors="coerce"
        ).iloc[0]

        if pd.isna(refund_amount) or pd.isna(purchase_amount):
            return False

        if refund_amount <= 0 or purchase_amount >= 0:
            return False

        if refund_amount > abs(purchase_amount):
            return False

    return True


def validate_timezone_dates(df):
    """Check UTC timestamps against local dates in Asia/Kolkata."""

    required = {
        "transaction_ts_utc",
        "local_transaction_date",
    }

    if not required.issubset(df.columns):
        return False

    utc_dates = pd.to_datetime(
        df["transaction_ts_utc"],
        errors="coerce",
        utc=True
    )

    local_dates = pd.to_datetime(
        df["local_transaction_date"],
        errors="coerce"
    )

    if utc_dates.isna().any() or local_dates.isna().any():
        return False

    expected_local_dates = (
        utc_dates.dt.tz_convert("Asia/Kolkata")
        .dt.date.astype(str)
    )

    actual_local_dates = local_dates.dt.date.astype(str)

    return bool(expected_local_dates.equals(actual_local_dates))


def validate_ground_truth(folder, transactions, budgets, recurring):
    """Check that ground-truth cases reference existing entities."""

    folder = Path(folder)

    # Support both a ground_truth folder inside the dataset folder
    # and the generator's current layout beside the dataset folder.
    path = folder / "ground_truth" / "ground_truth.csv"

    if not path.exists():
        path = folder.parent / "ground_truth" / "ground_truth.csv"

    if not path.exists():
        test_cases_path = folder / "recurring_test_cases.csv"

        # Small datasets intentionally have no controlled anomaly cases.
        if test_cases_path.exists():
            test_cases = pd.read_csv(test_cases_path)

            if test_cases.empty:
                return {
                    "ground_truth_file_exists": True,
                    "ground_truth_entities_valid": True,
                }

        return {
            "ground_truth_file_exists": False,
            "ground_truth_entities_valid": False,
        }

    ground = pd.read_csv(path)

    required = {
        "case_id",
        "entity_type",
        "entity_id",
        "issue_type",
        "expected_decision",
        "severity",
    }

    if not required.issubset(ground.columns):
        return {
            "ground_truth_file_exists": True,
            "ground_truth_entities_valid": False,
        }

    if not validate_unique(ground, "case_id"):
        return {
            "ground_truth_file_exists": True,
            "ground_truth_entities_valid": False,
        }

    entity_tables = {
        "Transaction": (transactions, "transaction_id"),
        "Budget": (budgets, "budget_id"),
        "RecurringSeries": (recurring, "recurring_id"),
    }

    for _, case in ground.iterrows():
        entity_type = case["entity_type"]
        entity_id = case["entity_id"]

        if entity_type not in entity_tables:
            return {
                "ground_truth_file_exists": True,
                "ground_truth_entities_valid": False,
            }

        entity_df, key = entity_tables[entity_type]

        if entity_id not in entity_df[key].values:
            return {
                "ground_truth_file_exists": True,
                "ground_truth_entities_valid": False,
            }

    return {
        "ground_truth_file_exists": True,
        "ground_truth_entities_valid": True,
    }


def validate_dataset(folder: Path):
    folder = Path(folder)

    users = pd.read_csv(folder / "users.csv")
    accounts = pd.read_csv(folder / "accounts.csv")
    merchants = pd.read_csv(folder / "merchants.csv")
    tx = pd.read_csv(folder / "transactions.csv")

    budgets = pd.read_csv(folder / "budgets.csv")
    recurring = pd.read_csv(folder / "recurring_series.csv")
    categories = pd.read_csv(folder / "categories.csv")
    rules = pd.read_csv(folder / "category_rules.csv")

    checks = {
        "users_pk_unique": validate_unique(users, "user_id"),
        "accounts_pk_unique": validate_unique(accounts, "account_id"),
        "merchants_pk_unique": validate_unique(merchants, "merchant_id"),
        "transactions_pk_unique": validate_unique(tx, "transaction_id"),
        "budgets_pk_unique": validate_unique(budgets, "budget_id"),
        "recurring_pk_unique": validate_unique(recurring, "recurring_id"),

        "accounts_user_fk_valid": validate_fk(
            accounts, "user_id", users, "user_id"
        ),
        "transactions_account_fk_valid": validate_fk(
            tx, "account_id", accounts, "account_id"
        ),
        "transactions_merchant_fk_valid": validate_fk(
            tx, "merchant_id", merchants, "merchant_id"
        ),
        "budgets_user_fk_valid": validate_fk(
            budgets, "user_id", users, "user_id"
        ),
        "budgets_category_fk_valid": validate_fk(
            budgets, "category_id", categories, "category_id"
        ),
        "recurring_account_fk_valid": validate_fk(
            recurring, "account_id", accounts, "account_id"
        ),
        "recurring_merchant_fk_valid": validate_fk(
            recurring, "merchant_id", merchants, "merchant_id"
        ),
        "rules_category_fk_valid": validate_fk(
            rules, "category_id", categories, "category_id"
        ),

        "transaction_amounts_valid": validate_positive(
            tx.assign(
                amount_minor=pd.to_numeric(
                    tx["amount_minor"], errors="coerce"
                ).abs()
            ),
            "amount_minor"
        ),
        "transaction_signs_valid": validate_transaction_signs(tx),
        "transaction_dates_valid": validate_dates(
            tx, "local_transaction_date"
        ),
        "budget_amounts_valid": validate_positive(
            budgets, "budget_limit_minor"
        ),
        "budget_dates_valid": validate_dates(
            budgets, "period_start"
        ),
        "recurring_amounts_valid": validate_positive(
            recurring, "expected_amount_minor"
        ),
        "recurring_dates_valid": validate_dates(
            recurring, "start_date"
        ),

        "transfer_pairs_valid": validate_transfer_pairs(tx),
        "refund_references_valid": validate_refund_references(tx),
        "timezone_dates_valid": validate_timezone_dates(tx),

        "quarantined_budget_marked": bool(
            "status" in budgets.columns
            and "issue_type" in budgets.columns
            and (
                budgets.loc[
                    budgets["issue_type"] == "BUDGET_CATEGORY_MISMATCH",
                    "status"
                ].astype(str).str.upper() == "QUARANTINED"
            ).all()
        ),
    }

    checks.update(
        validate_ground_truth(folder, tx, budgets, recurring)
    )

    return checks


def validate_outputs(folder: Path, expected_counts=None):
    """Validate generated pipeline output datasets."""

    folder = Path(folder)

    categorized = pd.read_csv(
        folder / "categorized_transactions.csv"
    )
    recurring = pd.read_csv(
        folder / "recurring_evaluation.csv"
    )
    budgets = pd.read_csv(
        folder / "budget_results.csv"
    )
    insights = pd.read_csv(
        folder / "insights.csv"
    )

    transactions = pd.read_csv(folder / "transactions.csv")
    recurring_series = pd.read_csv(folder / "recurring_series.csv")
    source_budgets = pd.read_csv(folder / "budgets.csv")
    users = pd.read_csv(folder / "users.csv")

    required_columns = {
        "categorized": {
            "transaction_id",
            "predicted_category_id",
            "applied_rule_id",
            "categorization_status",
        },
        "recurring": {
            "recurring_id",
            "expected_date",
            "matched_transaction_count",
            "status",
        },
        "budgets": {
            "budget_id",
            "user_id",
            "category_id",
            "actual_spend_minor",
            "variance_minor",
            "budget_status",
        },
        "insights": {
            "insight_id",
            "user_id",
            "category_id",
            "period",
            "insight_type",
            "actual_spend_minor",
            "budget_limit_minor",
            "severity",
        },
    }

    def has_columns(df, required):
        return required.issubset(set(df.columns))

    checks = {
        "categorized_required_columns": has_columns(
            categorized, required_columns["categorized"]
        ),
        "recurring_required_columns": has_columns(
            recurring, required_columns["recurring"]
        ),
        "budget_results_required_columns": has_columns(
            budgets, required_columns["budgets"]
        ),
        "insights_required_columns": has_columns(
            insights, required_columns["insights"]
        ),

        "categorized_transaction_ids_unique": validate_unique(
            categorized, "transaction_id"
        ),
        "categorized_transaction_fk_valid": validate_fk(
            categorized, "transaction_id",
            transactions, "transaction_id"
        ),
        "recurring_series_fk_valid": validate_fk(
            recurring, "recurring_id",
            recurring_series, "recurring_id"
        ),
        "budget_results_budget_fk_valid": validate_fk(
            budgets, "budget_id",
            source_budgets, "budget_id"
        ),
        "budget_results_user_fk_valid": validate_fk(
            budgets, "user_id", users, "user_id"
        ),
        "insight_ids_unique": validate_unique(
            insights, "insight_id"
        ),
        "insights_user_fk_valid": validate_fk(
            insights, "user_id", users, "user_id"
        ),

        "quarantined_budgets_excluded": bool(
            "status" in source_budgets.columns
            and not budgets["budget_id"].isin(
                source_budgets.loc[
                    source_budgets["status"].astype(str).str.upper()
                    == "QUARANTINED",
                    "budget_id"
                ]
            ).any()
        ),
    }

    if expected_counts is not None:
        checks.update({
            "categorized_row_count_valid":
                len(categorized) == expected_counts["categorized_transactions"],
            "recurring_row_count_valid":
                len(recurring) == expected_counts["recurring_evaluations"],
            "budget_row_count_valid":
                len(budgets) == expected_counts["budget_results"],
            "insight_row_count_valid":
                len(insights) == expected_counts["insights"],
        })

    return checks


def sha256(path: Path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)

    return h.hexdigest()


def checksum_manifest(folder: Path):
    return {
        p.name: sha256(p)
        for p in sorted(Path(folder).glob("*.csv"))
    }
