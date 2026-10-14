import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
FUEL_DATA_PATH = BASE_DIR / "fuel_data" / "fuel-prices-for-be-assessment.csv"

# 50 states + DC. The CSV also contains Canadian provinces, which are dropped.
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
}

REQUIRED_COLUMNS = [
    "OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Retail Price",
]


def clean_text(value):
    """Strip and collapse whitespace (some cities contain trailing padding)."""
    return re.sub(r"\s+", " ", str(value)).strip()


def load_fuel_data(path=FUEL_DATA_PATH):
    """
    Return one clean row per truck stop (US only).

    The CSV repeats the same OPIS id several times (alternate names / several
    prices). We keep the lowest price per id, since that is what a driver
    choosing where to fill up would pay.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fuel-price dataset not found: {path}")

    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["Retail Price"] = pd.to_numeric(df["Retail Price"], errors="coerce")
    for col in ("Truckstop Name", "Address", "City", "State"):
        df[col] = df[col].fillna("").map(clean_text)
    df["State"] = df["State"].str.upper()

    df = df.dropna(subset=["OPIS Truckstop ID", "Retail Price"])
    df = df[(df["Retail Price"] > 0) & (df["City"] != "")]
    df = df[df["State"].isin(US_STATE_CODES)]

    df = (
        df.sort_values(["OPIS Truckstop ID", "Retail Price"])
        .drop_duplicates(subset="OPIS Truckstop ID", keep="first")
        .reset_index(drop=True)
    )
    df["OPIS Truckstop ID"] = df["OPIS Truckstop ID"].astype(int)
    return df
