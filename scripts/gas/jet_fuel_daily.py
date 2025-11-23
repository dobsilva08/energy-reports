#!/usr/bin/env python3
"""
Baixa preços de Jet Fuel (Kerosene de Aviação) usando o FRED.

Série padrão sugerida:
  - DJFUELUSGULF = US Gulf Coast Kerosene-Type Jet Fuel Spot Price (USD/gal)
    (ajuste se utilizar outra série; pode sobrescrever via --series-id ou env)

Requisitos:
 - FRED_API_KEY (no ambiente / secrets do GitHub)
 - requests, pandas

Saída:
 - CSV com colunas: date, price, source

Uso:
  python scripts/gas/jet_fuel_daily.py --out pipelines/gas/jet_fuel_daily.csv
"""

import argparse
import os
from datetime import datetime
import requests
import pandas as pd

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_jet_fuel_from_fred(
    api_key: str,
    series_id: str = "DJFUELUSGULF",
    observation_start: str = "2003-01-01",
) -> pd.DataFrame:
    """
    Busca Jet Fuel via FRED.

    Params:
      - series_id: ID da série no FRED (ex: DJFUELUSGULF)
      - observation_start: data inicial da série (YYYY-MM-DD)
    """

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start,
        # sem 'frequency' forçada; usa a que a série tiver
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

        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        rows.append(
            {
                "date": dt,
                "price": price,
                "source": f"FRED:{series_id}",
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Baixa preços de Jet Fuel via FRED.")
    parser.add_argument(
        "--out",
        required=True,
        help="Caminho do CSV de saída (ex: pipelines/gas/jet_fuel_daily.csv)",
    )
    parser.add_argument(
        "--series-id",
        default=os.environ.get("JET_FUEL_FRED_SERIES_ID", "DJFUELUSGULF"),
        help="ID da série no FRED (padrão: DJFUELUSGULF ou valor de JET_FUEL_FRED_SERIES_ID).",
    )
    parser.add_argument(
        "--start",
        default="2003-01-01",
        help="Data inicial (YYYY-MM-DD, default: 2003-01-01)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY não configurado no ambiente.")

    df = fetch_jet_fuel_from_fred(
        api_key=api_key,
        series_id=args.series_id,
        observation_start=args.start,
    )

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    df.to_csv(out_path, index=False)
    print(f"[JET FUEL] CSV salvo em {out_path}")
    print(f"[JET FUEL] Linhas: {len(df)} — Período {df['date'].min()} → {df['date'].max()}")


if __name__ == "__main__":
    main()
