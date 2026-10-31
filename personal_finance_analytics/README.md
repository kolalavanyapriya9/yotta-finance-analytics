# Personal Finance Analytics — Yottaflex Assignment Starter

A reproducible, synthetic-data starter implementation for transaction categorization, recurring payment analysis, household budget comparison, and insight generation.

## Stack
Python, Pandas, NumPy, pytest, SQLite-compatible SQL. No real customer or bank data is used.

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Generate a small dataset first
```bash
python -m src.generate_data --users 10 --transactions 1000 --seed 20261022 --out data/raw/demo
```
Full requested volume:
```bash
python -m src.generate_data --users 1000 --transactions 500000 --seed 20261022 --out data/raw/full
```
The generator writes the separate ground-truth file to `data/ground_truth/ground_truth.csv`.

## Run processing
```bash
python -c "import pandas as pd; from src.categorize import categorize; from src.recurring import evaluate_recurring; from src.budgets import compare_budgets; from src.insights import build_insights; p='data/raw/demo/'; t=pd.read_csv(p+'transactions.csv'); m=pd.read_csv(p+'merchants.csv'); r=pd.read_csv(p+'category_rules.csv'); b=pd.read_csv(p+'budgets.csv'); s=pd.read_csv(p+'recurring_series.csv'); c=categorize(t,m,r); c.to_csv(p+'categorized_transactions.csv',index=False); rec=evaluate_recurring(t,s); rec.to_csv(p+'recurring_evaluation.csv',index=False); br=compare_budgets(t,b); br.to_csv(p+'budget_results.csv',index=False); build_insights(br).to_csv(p+'insights.csv',index=False)"
python -m src.export_data --folder data/raw/demo
python -m src.validate
```
Note: run the validation module as a Python import or use the helper snippet below; the starter `validate_dataset` accepts a folder path:
```bash
python -c "from pathlib import Path; from src.validate import validate_dataset; print(validate_dataset(Path('data/raw/demo')))"
```

## Tests
```bash
pytest -q
```

## Reproducibility
Run generation twice with the same seed into separate output folders, then compare CSV checksums using `src.validate.checksum_manifest`. Ensure output directories are separate and compare deterministic data files only.

## Important implementation notes / limitations
- This is a starter project, not a fully production-hardened banking platform.
- The generator creates synthetic rows with deterministic seed and IDs. It produces a labelled anomaly manifest separately; review the issue-injection logic and extend it to construct semantically exact anomaly examples for your final submission.
- Refund linking to original purchases, paired transfer reconciliation, timezone edge-case construction, rule versioning, and complete lifecycle event population are extension tasks to finish and document.
- The current recurring evaluator is a transparent baseline and can report false matches when multiple same-merchant payments occur in one month. Improve it with amount tolerance, date tolerance, and explicit membership linking.
- Budget aggregation should be reviewed and extended for unmatched refunds, account/user relationships, and your chosen net-spend policy.
- Run and report actual metrics; do not claim results that were not measured.
- Keep ground truth outside all prediction inputs.
