#!/usr/bin/env python3
"""
Baixa preços diários de ULSD / Heating Oil (HO1 proxy) usando o FRED.
Série padrão:
  - DDFUELUSGASDOWN = Ultra-Low Sulfur Diesel (ULSD) NY Harbor Spot Price

Requisitos:
 - FRED_API_KEY (já existe no repositório)
 - requests, pandas

Saída:
 - CSV com colunas: date, price, source
"""

import argparse
import os
from datetime import datetime
import requests
import pandas as pd

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_ulsd_from_fred(api_key: str,
                         series_id: str = "DDFUELUSGASDOWN",
                         observation_start: str = "2003-01-01") -> pd.DataFrame:

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start,
        "frequency": "d",
    }

    resp = requests.get(FRED_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    observations = data.get("observations", [])

    rows = []
    for obs in observations:
        date_str = obs.get("date")
        value_str = obs.get("value")

        if value_str in (None, ".", ""):
            continue

        try:
            price = float(value_str)
        except ValueError:
            continue

        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        rows.append(
            {
                "date": date,
                "price": price,
                "source": f"FRED:{series_id}",
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Baixa preços diários de ULSD (Heating Oil).")
    parser.add_argument("--out", required=True, help="Caminho do CSV de saída")
    parser.add_argument(
        "--series-id",
        default=os.environ.get("ULSD_FRED_SERIES_ID", "DDFUELUSGASDOWN"),
        help="ID da série no FRED (padrão: DDFUELUSGASDOWN)",
    )
    parser.add_argument(
        "--start",
        default="2003-01-01",
        help="Data inicial (YYYY-MM-DD)",
    )

    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY não configurado no ambiente.")

    df = fetch_ulsd_from_fred(
        api_key=api_key,
        series_id=args.series_id,
        observation_start=args.start,
    )

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    df.to_csv(out_path, index=False)
    print(f"[ULSD] CSV salvo em {out_path}")
    print(f"[ULSD] Linhas: {len(df)} — Período {df['date'].min()} → {df['date'].max()}")


if __name__ == "__main__":
    main()
