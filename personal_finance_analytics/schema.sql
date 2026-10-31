PRAGMA foreign_keys = ON;

CREATE TABLE UserProfile (
  user_id TEXT PRIMARY KEY,
  household_size INTEGER NOT NULL CHECK(household_size BETWEEN 1 AND 20),
  city TEXT NOT NULL,
  timezone TEXT NOT NULL,
  created_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE'))
);
CREATE TABLE Account (
  account_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES UserProfile(user_id),
  account_type TEXT NOT NULL,
  currency TEXT NOT NULL,
  opening_balance_minor INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('ACTIVE','CLOSED'))
);
CREATE TABLE Merchant (
  merchant_id TEXT PRIMARY KEY,
  merchant_name TEXT NOT NULL,
  merchant_type TEXT NOT NULL,
  aliases TEXT
);
CREATE TABLE Category (
  category_id TEXT PRIMARY KEY,
  category_name TEXT NOT NULL UNIQUE,
  category_type TEXT NOT NULL CHECK(category_type IN ('INCOME','EXPENSE','TRANSFER','REFUND')),
  active INTEGER NOT NULL
);
CREATE TABLE CategoryRule (
  rule_id TEXT PRIMARY KEY,
  merchant_type TEXT NOT NULL,
  category_id TEXT NOT NULL REFERENCES Category(category_id),
  priority INTEGER NOT NULL,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  active INTEGER NOT NULL
);
CREATE TABLE "Transaction" (
  transaction_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES Account(account_id),
  merchant_id TEXT REFERENCES Merchant(merchant_id),
  merchant_descriptor TEXT NOT NULL,
  transaction_ts_utc TEXT NOT NULL,
  local_transaction_date TEXT NOT NULL,
  amount_minor INTEGER NOT NULL,
  currency TEXT NOT NULL,
  transaction_type TEXT NOT NULL,
  category_id TEXT REFERENCES Category(category_id),
  status TEXT NOT NULL CHECK(status IN ('PENDING','POSTED','REVERSED')),
  issue_type TEXT,
  transfer_group_id TEXT,
  original_transaction_id TEXT,
    FOREIGN KEY (original_transaction_id)
    REFERENCES "Transaction"(transaction_id)
    DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE Budget (
  budget_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES UserProfile(user_id),
  category_id TEXT NOT NULL REFERENCES Category(category_id),
  period_start TEXT NOT NULL,
  budget_limit_minor INTEGER NOT NULL CHECK(budget_limit_minor >= 0),
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  issue_type TEXT
);
CREATE TABLE RecurringSeries (
  recurring_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES UserProfile(user_id),
  account_id TEXT NOT NULL REFERENCES Account(account_id),
  merchant_id TEXT NOT NULL REFERENCES Merchant(merchant_id),
  series_type TEXT NOT NULL,
  frequency TEXT NOT NULL,
  expected_amount_minor INTEGER NOT NULL,
  expected_day INTEGER NOT NULL CHECK(expected_day BETWEEN 1 AND 28),
  start_date TEXT NOT NULL,
  end_date TEXT,
  status TEXT NOT NULL
);
CREATE TABLE Insight (
  insight_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES UserProfile(user_id),
  category_id TEXT REFERENCES Category(category_id),
  period TEXT NOT NULL,
  insight_type TEXT NOT NULL,
  actual_spend_minor INTEGER,
  budget_limit_minor INTEGER,
  severity TEXT NOT NULL
);
-- Production extension: append-only EntityEvent table and RecurringTransaction bridge table.
CREATE TABLE EntityEvent (
  event_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  previous_state TEXT,
  new_state TEXT NOT NULL,
  event_ts_utc TEXT NOT NULL,
  actor TEXT NOT NULL,
  reason TEXT,
  correlation_id TEXT
);
CREATE TABLE RecurringTransaction (
  recurring_id TEXT NOT NULL REFERENCES RecurringSeries(recurring_id),
  transaction_id TEXT NOT NULL REFERENCES "Transaction"(transaction_id),
  membership_status TEXT NOT NULL,
  PRIMARY KEY(recurring_id, transaction_id)
);
