# Data dictionary (starter)

All monetary amounts are integer minor units (INR paise). Dates are ISO-8601. UTC timestamps end in `Z`. Synthetic records only.

| Entity | Primary key | Important fields | Required validation |
|---|---|---|---|
| UserProfile | user_id | household_size, city, timezone, status | unique ID; household size 1–20; valid timezone |
| Account | account_id | user_id, account_type, currency, opening_balance_minor, status | user FK; nonnegative opening balance |
| Merchant | merchant_id | merchant_name, merchant_type, aliases | unique ID; normalized aliases |
| Transaction | transaction_id | account_id, merchant_id, timestamp, amount_minor, type, status | account/merchant/category FKs; signed amount policy |
| Category | category_id | category_name, category_type, active | unique ID/name; allowed type |
| CategoryRule | rule_id | merchant_type, category_id, priority, effective dates | category FK; valid date range |
| Budget | budget_id | user_id, category_id, period_start, budget_limit_minor | user/category FKs; nonnegative limit |
| RecurringSeries | recurring_id | user_id, account_id, merchant_id, frequency, expected amount/date | valid parent FKs; expected day 1–28 |
| Insight | insight_id | user_id, category_id, period, type, severity | valid user/category FKs |

## Relationships and cardinality
- UserProfile 1:N Account.
- Account 1:N Transaction.
- Merchant 1:N Transaction (optional merchant on a transaction).
- Category 1:N CategoryRule and 1:N Budget.
- UserProfile 1:N Budget and 1:N RecurringSeries.
- RecurringSeries N:M Transaction through RecurringTransaction.
- UserProfile 1:N Insight; Category 1:N Insight (category optional).
- EntityEvent is an append-only polymorphic event history.

## Lifecycle and effective dating
Use ACTIVE/INACTIVE or POSTED/PENDING/REVERSED states as appropriate. CategoryRule has effective_from/effective_to. Record state changes as EntityEvent rows; do not overwrite audit history. This starter uses one annual effective period and can be extended to versioned rules.
