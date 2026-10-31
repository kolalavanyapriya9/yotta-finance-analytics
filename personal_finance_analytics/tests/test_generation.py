from pathlib import Path
import pandas as pd
from src.generate_data import generate
from src.validate import validate_dataset

def test_small_generation(tmp_path):
    out=tmp_path/"raw"/"demo"
    generate(3,25,20261022,out)
    assert len(pd.read_csv(out/"users.csv"))==3
    assert len(pd.read_csv(out/"transactions.csv"))==25
    assert all(validate_dataset(out).values())
