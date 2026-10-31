"""Rule-based categorization with explicit decisions and traceability."""
import pandas as pd

def categorize(transactions: pd.DataFrame, merchants: pd.DataFrame, rules: pd.DataFrame) -> pd.DataFrame:
    result=transactions.merge(merchants[["merchant_id","merchant_type"]],on="merchant_id",how="left",validate="many_to_one")
    active=rules[rules["active"].astype(bool)].sort_values(["priority","rule_id"],ascending=[False,True])
    mapping=active.drop_duplicates("merchant_type").set_index("merchant_type")
    def decide(row):
        if row["transaction_type"] in ("TRANSFER_IN","TRANSFER_OUT"):
            return pd.Series(["CAT-TRANSFER","TRANSFER_RULE","TRANSFER_EXCLUDED"])
        if row["transaction_type"]=="REFUND":
            return pd.Series(["CAT-REFUND","REFUND_RULE","REFUND_REVIEW"])
        mtype=row.get("merchant_type")
        if pd.notna(mtype) and mtype in mapping.index:
            r=mapping.loc[mtype]
            return pd.Series([r["category_id"],r["rule_id"],"RULE_MATCHED"])
        return pd.Series(["CAT-OTHER","FALLBACK","NEEDS_REVIEW"])
    result[["predicted_category_id","applied_rule_id","categorization_status"]]=result.apply(decide,axis=1)
    return result.drop(columns=["merchant_type"])
