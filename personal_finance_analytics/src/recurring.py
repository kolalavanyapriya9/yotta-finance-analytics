
"""Evaluate recurring payments and identify payment exceptions."""

import pandas as pd


DATE_TOLERANCE_DAYS = 7
AMOUNT_TOLERANCE = 0.05


def evaluate_recurring(
    transactions: pd.DataFrame,
    recurring_series: pd.DataFrame
) -> pd.DataFrame:

    tx = transactions.copy()

    tx["date"] = pd.to_datetime(
        tx["local_transaction_date"],
        errors="coerce"
    )

    tx["amount_abs"] = pd.to_numeric(
        tx["amount_minor"],
        errors="coerce"
    ).abs()

    tx = tx.dropna(subset=["date", "amount_abs"])

    rows = []

    for series in recurring_series.itertuples(index=False):

        subset = tx[
            (tx["account_id"] == series.account_id)
            & (tx["merchant_id"] == series.merchant_id)
            & (tx["transaction_type"] != "REFUND")
            & (tx["status_y"] == "POSTED"
               if "status_y" in tx.columns
               else tx["status"] == "POSTED")
        ].copy()

        # Small datasets may contain only part of a recurring series.
        # Do not evaluate months outside the observed transaction period.
        if subset.empty:
            continue

        first_month = subset["date"].min().to_period("M")
        last_month = subset["date"].max().to_period("M")

        expected_dates = (
            pd.date_range(
                start=series.start_date,
                end=series.end_date,
                freq="MS"
            )
            + pd.to_timedelta(
                int(series.expected_day) - 1,
                unit="D"
            )
        )

        for expected_date in expected_dates:

            expected_month = expected_date.to_period("M")

            if not first_month <= expected_month <= last_month:
                continue

            # Match transactions within seven days of the expected date.
            candidates = subset[
                (subset["date"].dt.to_period("M") == expected_month)
                &
                (
                (subset["date"] - expected_date).dt.days.abs()
                <= DATE_TOLERANCE_DAYS
                )
            ].copy()

            count = len(candidates)

            if count == 0:
                status = "POSSIBLE_MISSED"

            elif count > 1:
                status = "DUPLICATE"

            else:
                actual = candidates.iloc[0]

                expected_amount = abs(
                    float(series.expected_amount_minor)
                )

                actual_amount = float(actual["amount_abs"])

                if expected_amount == 0:
                    amount_difference = 0
                else:
                    amount_difference = (
                        abs(actual_amount - expected_amount)
                        / expected_amount
                    )

                if amount_difference > AMOUNT_TOLERANCE:
                    status = "AMOUNT_MISMATCH"

                elif actual["date"] > expected_date:
                    status = "DELAYED"

                else:
                    status = "PAID"

            rows.append({
                "recurring_id": series.recurring_id,
                "expected_date": expected_date.date().isoformat(),
                "matched_transaction_count": count,
                "status": status
            })

    return pd.DataFrame(
        rows,
        columns=[
            "recurring_id",
            "expected_date",
            "matched_transaction_count",
            "status"
        ]
    )
