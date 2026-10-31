"""Evaluate recurring detection and controlled ground-truth scenarios."""

from zoneinfo import ZoneInfo

import pandas as pd


EXPECTED_RECURRING_STATUS = {
    "MISSING": "POSSIBLE_MISSED",
    "DELAYED": "DELAYED",
    "AMOUNT_MISMATCH": "AMOUNT_MISMATCH",
    "DUPLICATE": "DUPLICATE",
}


def evaluate_recurring_cases(
    test_cases: pd.DataFrame,
    recurring_results: pd.DataFrame,
):
    """Compare recurring test cases with detector predictions."""

    required_test = {"recurring_id", "expected_date", "case"}
    required_results = {
        "recurring_id",
        "expected_date",
        "matched_transaction_count",
        "status",
    }

    if not required_test.issubset(test_cases.columns):
        raise ValueError("Recurring test cases are missing required columns.")

    if not required_results.issubset(recurring_results.columns):
        raise ValueError("Recurring results are missing required columns.")

    tests = test_cases.copy()
    results = recurring_results.copy()

    tests["expected_status"] = tests["case"].map(EXPECTED_RECURRING_STATUS)
    if tests["expected_status"].isna().any():
        raise ValueError("Unknown recurring test case found.")

    tests["expected_date"] = pd.to_datetime(tests["expected_date"]).dt.date
    results["expected_date"] = pd.to_datetime(results["expected_date"]).dt.date

    evaluated = tests.merge(
        results,
        on=["recurring_id", "expected_date"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )

    evaluated["prediction_found"] = evaluated["_merge"] == "both"
    evaluated["correct"] = (
        evaluated["prediction_found"]
        & (evaluated["status"] == evaluated["expected_status"])
    )
    evaluated["correct"] = evaluated["correct"].astype(bool)

    total = len(evaluated)
    correct = int(evaluated["correct"].sum())

    metrics = {
        "total_cases": total,
        "correct_cases": correct,
        "incorrect_cases": total - correct,
        "accuracy_pct": round(correct / total * 100, 2) if total else 0.0,
    }

    details = evaluated[
        [
            "recurring_id",
            "expected_date",
            "case",
            "expected_status",
            "status",
            "matched_transaction_count",
            "prediction_found",
            "correct",
        ]
    ].copy()

    return details, metrics


def evaluate_ground_truth_cases(
    ground_truth: pd.DataFrame,
    transactions: pd.DataFrame,
    recurring_results: pd.DataFrame,
    budgets: pd.DataFrame,
    budget_results: pd.DataFrame,
    categorized_transactions: pd.DataFrame | None = None,
    timezone_name: str = "Asia/Kolkata",
):
    """Evaluate the five controlled cases recorded in ground_truth.csv.

    These checks validate observable pipeline outcomes. They are controlled
    fixture checks, not a claim of general model or production accuracy.
    """

    required_ground_truth = {
        "case_id", "entity_type", "entity_id", "issue_type",
        "expected_decision", "expected_date", "related_entity_id",
    }
    if not required_ground_truth.issubset(ground_truth.columns):
        raise ValueError("Ground-truth file is missing required columns.")

    required_transactions = {
        "transaction_id", "account_id", "merchant_id",
        "transaction_ts_utc", "local_transaction_date",
        "amount_minor", "transaction_type", "transfer_group_id",
        "original_transaction_id",
    }
    if not required_transactions.issubset(transactions.columns):
        raise ValueError("Transactions are missing required columns.")

    required_recurring = {"recurring_id", "expected_date", "status"}
    if not required_recurring.issubset(recurring_results.columns):
        raise ValueError("Recurring results are missing required columns.")

    required_budgets = {"budget_id", "status", "issue_type"}
    if not required_budgets.issubset(budgets.columns):
        raise ValueError("Budgets are missing required columns.")

    if "budget_id" not in budget_results.columns:
        raise ValueError("Budget results are missing budget_id.")

    tx = transactions.copy()
    tx["transaction_id"] = tx["transaction_id"].astype(str)
    tx_lookup = tx.set_index("transaction_id", drop=False)

    budget_lookup = budgets.copy()
    budget_lookup["budget_id"] = budget_lookup["budget_id"].astype(str)
    budget_lookup = budget_lookup.set_index("budget_id", drop=False)

    result_budget_ids = set(budget_results["budget_id"].astype(str))
    recurring = recurring_results.copy()
    recurring["expected_date"] = pd.to_datetime(
        recurring["expected_date"], errors="coerce"
    ).dt.date

    categorized_lookup = None
    if categorized_transactions is not None:
        if not {"transaction_id", "predicted_category_id"}.issubset(
            categorized_transactions.columns
        ):
            raise ValueError(
                "Categorized transactions need transaction_id and predicted_category_id."
            )
        cat = categorized_transactions.copy()
        cat["transaction_id"] = cat["transaction_id"].astype(str)
        categorized_lookup = cat.set_index("transaction_id", drop=False)

    rows = []

    for case in ground_truth.to_dict("records"):
        case_id = str(case["case_id"])
        entity_type = str(case["entity_type"])
        entity_id = str(case["entity_id"])
        issue_type = str(case["issue_type"])
        related_id = (
            None if pd.isna(case["related_entity_id"])
            else str(case["related_entity_id"])
        )
        expected_date = pd.to_datetime(case["expected_date"]).date()

        checks = {}
        actual_observation = ""

        if issue_type == "TRANSFER_DOUBLE_COUNT":
            transfer = tx_lookup.loc[entity_id] if entity_id in tx_lookup.index else None
            partner = (
                tx_lookup.loc[related_id]
                if related_id is not None and related_id in tx_lookup.index
                else None
            )
            if isinstance(transfer, pd.DataFrame):
                transfer = transfer.iloc[0]
            if isinstance(partner, pd.DataFrame):
                partner = partner.iloc[0]

            checks["both_transfer_rows_exist"] = transfer is not None and partner is not None
            if checks["both_transfer_rows_exist"]:
                checks["same_transfer_group"] = (
                    pd.notna(transfer["transfer_group_id"])
                    and transfer["transfer_group_id"] == partner["transfer_group_id"]
                )
                checks["opposite_transfer_types"] = {
                    str(transfer["transaction_type"]), str(partner["transaction_type"])
                } == {"TRANSFER_OUT", "TRANSFER_IN"}
                checks["amounts_offset"] = (
                    int(transfer["amount_minor"]) + int(partner["amount_minor"]) == 0
                )
                if categorized_lookup is not None:
                    cat_ids = []
                    for tid in (entity_id, related_id):
                        if tid in categorized_lookup.index:
                            value = categorized_lookup.loc[tid]
                            if isinstance(value, pd.DataFrame):
                                value = value.iloc[0]
                            cat_ids.append(str(value["predicted_category_id"]))
                    checks["both_categorized_as_transfer"] = (
                        len(cat_ids) == 2 and all(x == "CAT-TRANSFER" for x in cat_ids)
                    )
            actual_observation = "Paired transfer integrity and transfer categorization checked."

        elif issue_type == "REFUND_AS_NEW_EXPENSE":
            refund = tx_lookup.loc[entity_id] if entity_id in tx_lookup.index else None
            original = (
                tx_lookup.loc[related_id]
                if related_id is not None and related_id in tx_lookup.index
                else None
            )
            if isinstance(refund, pd.DataFrame):
                refund = refund.iloc[0]
            if isinstance(original, pd.DataFrame):
                original = original.iloc[0]

            checks["refund_and_original_exist"] = refund is not None and original is not None
            if checks["refund_and_original_exist"]:
                checks["refund_links_to_original"] = (
                    str(refund["original_transaction_id"]) == related_id
                )
                checks["correct_transaction_types"] = (
                    str(refund["transaction_type"]) == "REFUND"
                    and str(original["transaction_type"]) == "PURCHASE"
                )
                checks["same_account_and_merchant"] = (
                    str(refund["account_id"]) == str(original["account_id"])
                    and str(refund["merchant_id"]) == str(original["merchant_id"])
                )
                checks["refund_does_not_exceed_purchase"] = (
                    int(refund["amount_minor"]) > 0
                    and int(original["amount_minor"]) < 0
                    and int(refund["amount_minor"]) <= abs(int(original["amount_minor"]))
                )
            actual_observation = "Refund linkage and offset constraints checked."

        elif issue_type == "RECURRING_SERIES_SKIP":
            matches = recurring[
                (recurring["recurring_id"].astype(str) == entity_id)
                & (recurring["expected_date"] == expected_date)
            ]
            expected_status = "POSSIBLE_MISSED"
            checks["recurring_evaluation_found"] = len(matches) == 1
            if len(matches) == 1:
                checks["flagged_as_possible_missed"] = (
                    str(matches.iloc[0]["status"]) == expected_status
                )
            actual_observation = "Recurring evaluation checked against expected missed-payment flag."

        elif issue_type == "TIMEZONE_BOUNDARY":
            transaction = (
                tx_lookup.loc[entity_id] if entity_id in tx_lookup.index else None
            )
            if isinstance(transaction, pd.DataFrame):
                transaction = transaction.iloc[0]
            checks["transaction_exists"] = transaction is not None
            if transaction is not None:
                utc_timestamp = pd.to_datetime(
                    transaction["transaction_ts_utc"], utc=True, errors="coerce"
                )
                checks["utc_timestamp_valid"] = not pd.isna(utc_timestamp)
                if not pd.isna(utc_timestamp):
                    derived_local_date = (
                        utc_timestamp.tz_convert(ZoneInfo(timezone_name)).date()
                    )
                    checks["local_date_matches_expected"] = (
                        derived_local_date == expected_date
                    )
                    recorded_date = pd.to_datetime(
                        transaction["local_transaction_date"], errors="coerce"
                    )
                    checks["recorded_local_date_matches"] = (
                        not pd.isna(recorded_date)
                        and recorded_date.date() == expected_date
                    )
            actual_observation = "UTC-to-local date conversion checked."

        elif issue_type == "BUDGET_CATEGORY_MISMATCH":
            budget = (
                budget_lookup.loc[entity_id]
                if entity_id in budget_lookup.index
                else None
            )
            if isinstance(budget, pd.DataFrame):
                budget = budget.iloc[0]
            checks["budget_exists"] = budget is not None
            if budget is not None:
                checks["budget_is_quarantined"] = (
                    str(budget["status"]).upper() == "QUARANTINED"
                )
                checks["budget_issue_type_matches"] = (
                    str(budget["issue_type"]) == "BUDGET_CATEGORY_MISMATCH"
                )
            checks["quarantined_budget_excluded_from_results"] = (
                entity_id not in result_budget_ids
            )
            actual_observation = "Budget quarantine and exclusion from budget results checked."

        else:
            raise ValueError(f"Unsupported ground-truth issue_type: {issue_type}")

        passed = bool(checks) and all(bool(value) for value in checks.values())
        rows.append({
            "case_id": case_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "issue_type": issue_type,
            "expected_decision": case["expected_decision"],
            "expected_date": str(expected_date),
            "checks": checks,
            "actual_observation": actual_observation,
            "checks_passed": sum(bool(v) for v in checks.values()),
            "checks_total": len(checks),
            "correct": passed,
        })

    details = pd.DataFrame(rows)
    total = len(details)
    correct = int(details["correct"].sum()) if total else 0
    metrics = {
        "total_cases": total,
        "correct_cases": correct,
        "incorrect_cases": total - correct,
        "accuracy_pct": round(correct / total * 100, 2) if total else 0.0,
        "checks_passed": int(details["checks_passed"].sum()) if total else 0,
        "checks_total": int(details["checks_total"].sum()) if total else 0,
    }
    return details, metrics
