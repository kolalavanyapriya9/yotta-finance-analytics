import pandas as pd
from src.categorize import categorize
from src.budgets import compare_budgets

def test_transfer_and_refund_categorization():
    tx=pd.DataFrame([
      {"transaction_id":"1","merchant_id":"MER-000009","transaction_type":"TRANSFER_OUT"},
      {"transaction_id":"2","merchant_id":"MER-000001","transaction_type":"REFUND"}
    ])
    merchants=pd.DataFrame([{"merchant_id":"MER-000009","merchant_type":"TRANSFER"},
                            {"merchant_id":"MER-000001","merchant_type":"GROCERIES"}])
    rules=pd.DataFrame(columns=["active","priority","rule_id","merchant_type","category_id"])
    got=categorize(tx,merchants,rules)
    assert got.loc[0,"predicted_category_id"]=="CAT-TRANSFER"
    assert got.loc[1,"predicted_category_id"]=="CAT-REFUND"
