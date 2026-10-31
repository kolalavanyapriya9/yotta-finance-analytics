"""Run the complete personal finance analytics pipeline."""

import argparse
import json
from pathlib import Path

import pandas as pd

from src.categorize import categorize
from src.recurring import evaluate_recurring
from src.evaluate import (
    evaluate_recurring_cases,
    evaluate_ground_truth_cases,
)
from src.budgets import compare_budgets
from src.insights import build_insights
from src.validate import validate_dataset, validate_outputs
from src.export_data import export_json


def _write_json(path: Path, data: dict):
    """Write JSON with safe conversion for NumPy/Pandas scalar values."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, default=str)


def run_pipeline(folder: Path):
    folder = Path(folder)

    print("\n========== PERSONAL FINANCE ANALYTICS ==========")

    print("\n[1/7] Loading input datasets...")

    transactions = pd.read_csv(folder / "transactions.csv")
    accounts = pd.read_csv(folder / "accounts.csv")
    merchants = pd.read_csv(folder / "merchants.csv")
    rules = pd.read_csv(folder / "category_rules.csv")
    budgets = pd.read_csv(folder / "budgets.csv")
    recurring_series = pd.read_csv(folder / "recurring_series.csv")

    ground_truth_path = folder / "ground_truth" / "ground_truth.csv"
    if not ground_truth_path.exists():
        ground_truth_path = folder.parent / "ground_truth" / "ground_truth.csv"
    if not ground_truth_path.exists():
        raise FileNotFoundError(
            "ground_truth.csv not found in folder/ground_truth or sibling ground_truth folder."
        )
    ground_truth = pd.read_csv(ground_truth_path)

    print(f"Transactions loaded: {len(transactions)}")
    print(f"Ground-truth cases loaded: {len(ground_truth)}")

    print("\n[2/7] Categorizing transactions...")

    categorized = categorize(transactions, merchants, rules)
    categorized.to_csv(folder / "categorized_transactions.csv", index=False)
    print(f"Categorized transactions: {len(categorized)}")

    print("\n[3/7] Evaluating recurring payments...")

    recurring_results = evaluate_recurring(transactions, recurring_series)
    recurring_results.to_csv(folder / "recurring_evaluation.csv", index=False)
    print(f"Recurring evaluations: {len(recurring_results)}")

    print("\nEvaluating recurring test cases...")

    recurring_test_cases = pd.read_csv(folder / "recurring_test_cases.csv")
    recurring_case_details, recurring_metrics = evaluate_recurring_cases(
        recurring_test_cases, recurring_results
    )
    recurring_case_details.to_csv(
        folder / "recurring_case_evaluation.csv", index=False
    )
    _write_json(folder / "evaluation_report.json", recurring_metrics)

    print(f"Recurring test cases: {recurring_metrics['total_cases']}")
    print(f"Correct predictions: {recurring_metrics['correct_cases']}")
    print(f"Incorrect predictions: {recurring_metrics['incorrect_cases']}")
    print(f"Recurring case accuracy: {recurring_metrics['accuracy_pct']}%")

    print("\n[4/7] Comparing budgets...")

    budget_results = compare_budgets(categorized, budgets, accounts)
    budget_results.to_csv(folder / "budget_results.csv", index=False)
    print(f"Budget records evaluated: {len(budget_results)}")

    print("\n[5/7] Generating insights...")

    insights = build_insights(budget_results)
    insights.to_csv(folder / "insights.csv", index=False)
    print(f"Insights generated: {len(insights)}")

    print("\n[6/7] Evaluating ground-truth cases...")

    ground_truth_details, ground_truth_metrics = evaluate_ground_truth_cases(
        ground_truth=ground_truth,
        transactions=transactions,
        recurring_results=recurring_results,
        budgets=budgets,
        budget_results=budget_results,
        categorized_transactions=categorized,
    )
    ground_truth_details.to_csv(
        folder / "ground_truth_case_evaluation.csv", index=False
    )
    _write_json(
        folder / "ground_truth_evaluation_report.json",
        ground_truth_metrics,
    )

    for _, row in ground_truth_details.iterrows():
        status = "PASS" if row["correct"] else "FAIL"
        print(f"{row['case_id']} ({row['issue_type']}): {status}")

    print(
        "Ground-truth evaluation: "
        f"{ground_truth_metrics['correct_cases']}/"
        f"{ground_truth_metrics['total_cases']} cases passed "
        f"({ground_truth_metrics['accuracy_pct']}%)"
    )

    print("\nValidating dataset and pipeline outputs...")

    source_validation = validate_dataset(folder)
    output_validation = validate_outputs(
        folder,
        expected_counts={
            "categorized_transactions": len(categorized),
            "recurring_evaluations": len(recurring_results),
            "budget_results": len(budget_results),
            "insights": len(insights),
        },
    )

    validation_results = {**source_validation, **output_validation}
    for check, result in validation_results.items():
        print(f"{check}: {'PASS' if result else 'FAIL'}")

    validation_passed = all(validation_results.values())

    print("\n[7/7] Exporting CSV files to JSON...")
    export_json(folder)

    report = {
        "pipeline_status": (
            "SUCCESS" if validation_passed and ground_truth_metrics["incorrect_cases"] == 0
            else "VALIDATION_FAILED"
        ),
        "input_counts": {
            "transactions": len(transactions),
            "merchants": len(merchants),
            "category_rules": len(rules),
            "budgets": len(budgets),
            "recurring_series": len(recurring_series),
            "ground_truth_cases": len(ground_truth),
        },
        "output_counts": {
            "categorized_transactions": len(categorized),
            "recurring_evaluations": len(recurring_results),
            "recurring_case_evaluations": len(recurring_case_details),
            "ground_truth_case_evaluations": len(ground_truth_details),
            "budget_results": len(budget_results),
            "insights": len(insights),
        },
        "recurring_case_metrics": recurring_metrics,
        "ground_truth_metrics": ground_truth_metrics,
        "validation": validation_results,
        "validation_passed": validation_passed,
    }

    _write_json(folder / "pipeline_report.json", report)

    print("\n========== PIPELINE SUMMARY ==========")
    print(json.dumps(report, indent=4, default=str))
    print("\nPipeline execution completed!")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Personal Finance Analytics Pipeline"
    )
    parser.add_argument("--folder", type=Path, default=Path("data/raw/demo"))
    args = parser.parse_args()
    run_pipeline(args.folder)
