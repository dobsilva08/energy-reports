#!/usr/bin/env python3
"""
Busca múltiplas séries semanais da EIA e gera 3 CSVs:

 - /tmp/petroleum_crude.csv
 - /tmp/petroleum_products.csv
 - /tmp/gas_storage.csv

ENV necessárias (já configuradas como secrets no GitHub):
 - EIA_API_KEY
 - EIA_PETROLEUM_CRUDE_SERIES_ID      (ex: PET.WCESTUS1.W)
 - EIA_PETROLEUM_PRODUCTS_SERIES_ID   (ex: PET.STOCKUS1.W)
 - EIA_GAS_STORAGE_SERIES_ID          (ex: NG.NW2_EPG0_SWO_R48_BCF.W)
"""

import os
import sys
import requests
from datetime import datetime
import pandas as pd

API_KEY = os.getenv("EIA_API_KEY")
CRUDE_SERIES = os.getenv("EIA_PETROLEUM_CRUDE_SERIES_ID")
PRODUCTS_SERIES = os.getenv("EIA_PETROLEUM_PRODUCTS_SERIES_ID")
GAS_SERIES = os.getenv("EIA_GAS_STORAGE_SERIES_ID")

if not API_KEY or not CRUDE_SERIES or not PRODUCTS_SERIES or not GAS_SERIES:
    print(
        "Missing required environment variables. "
        "Set EIA_API_KEY, EIA_PETROLEUM_CRUDE_SERIES_ID, "
        "EIA_PETROLEUM_PRODUCTS_SERIES_ID, EIA_GAS_STORAGE_SERIES_ID.",
        file=sys.stderr,
    )
    sys.exit(2)


def fetch_series(series_id: str) -> dict:
    url = f"https://api.eia.gov/series/?api_key={API_KEY}&series_id={series_id}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_series_to_df(j: dict) -> pd.DataFrame:
    series_list = j.get("series", [])
    if not series_list:
        return pd.DataFrame()

    s0 = series_list[0]
    rows = []
    for entry in s0.get("data", []):
        date_raw, value = entry[0], entry[1]

        date = None
        for fmt in ("%Y%m%d", "%Y%m", "%Y-%m-%d", "%Y-%m"):
            try:
                date = datetime.strptime(str(date_raw), fmt).date()
                break
            except Exception:
                continue

        if date is None:
            date = str(date_raw)

        rows.append(
            {
                "date": date,
                "value": None if value in (None, "") else float(value),
                "series_id": s0.get("series_id"),
                "label": s0.get("name"),
                "retrieved_at": datetime.utcnow().isoformat(),
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


def save_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)
    print("WROTE", path)


def main() -> None:
    # crude
    j_crude = fetch_series(CRUDE_SERIES)
    df_crude = parse_series_to_df(j_crude)
    save_csv(df_crude, "/tmp/petroleum_crude.csv")

    # products
    j_products = fetch_series(PRODUCTS_SERIES)
    df_products = parse_series_to_df(j_products)
    save_csv(df_products, "/tmp/petroleum_products.csv")

    # gas
    j_gas = fetch_series(GAS_SERIES)
    df_gas = parse_series_to_df(j_gas)
    if not df_gas.empty:
        df_gas = df_gas.rename(columns={"value": "storage_bcf"})
    save_csv(df_gas, "/tmp/gas_storage.csv")


if __name__ == "__main__":
    main()
