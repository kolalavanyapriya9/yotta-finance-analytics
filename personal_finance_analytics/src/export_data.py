
"""Export generated CSV tables to JSON and SQLite."""

from pathlib import Path
import pandas as pd
import argparse
import sqlite3


CORE_TABLES = [
    ("users.csv", "UserProfile"),
    ("accounts.csv", "Account"),
    ("merchants.csv", "Merchant"),
    ("categories.csv", "Category"),
    ("category_rules.csv", "CategoryRule"),
    ("transactions.csv", "Transaction"),
    ("budgets.csv", "Budget"),
    ("recurring_series.csv", "RecurringSeries"),
    ("insights.csv", "Insight"),
]

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"


def export_json(folder: Path):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    # Export CSV files to JSON.
    for csv_path in folder.glob("*.csv"):
        if csv_path.name == "ground_truth.csv":
            continue

        df = pd.read_csv(csv_path)
        df.to_json(
            folder / (csv_path.stem + ".json"),
            orient="records",
            indent=2,
            date_format="iso",
        )

    # Export core CSV tables to SQLite.
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")

    db_path = folder / "personal_finance_analytics.db"

    # Remove an older database to prevent duplicate records.
    if db_path.exists():
        db_path.unlink()

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )

        for csv_name, table_name in CORE_TABLES:
            csv_path = folder / csv_name

            if not csv_path.exists():
                if csv_name == "insights.csv":
                    continue
                raise FileNotFoundError(
                    f"Required CSV not found: {csv_path}"
                )

            df = pd.read_csv(csv_path)

            # SQLite table names are safely quoted.
            quoted_table = '"' + table_name.replace('"', '""') + '"'

            df.to_sql(
                table_name,
                connection,
                if_exists="append",
                index=False,
                )

        # Verify foreign-key relationships.
        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise ValueError(
                f"Foreign-key violations found: {violations[:10]}"
            )

        # Print exported row counts.
        print("\nSQLite export summary:")
        for _, table_name in CORE_TABLES:
            quoted_table = '"' + table_name.replace('"', '""') + '"'
            count = connection.execute(
                f"SELECT COUNT(*) FROM {quoted_table}"
            ).fetchone()[0]
            print(f"{table_name}: {count}")

    print(f"\nSQLite database created: {db_path}")
    return db_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path("data/raw/demo"),
    )
    export_json(parser.parse_args().folder)
