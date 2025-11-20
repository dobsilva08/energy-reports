#!/usr/bin/env python3
"""
Busca múltiplas séries semanais da EIA e gera 3 CSVs:

 - /tmp/petroleum_crude.csv        -> estoques comerciais de crude (PET.WCESTUS1.W)
 - /tmp/petroleum_products.csv     -> estoques de crude + produtos (PET.WTTSTUS1.W)
 - /tmp/gas_storage.csv            -> working gas in storage (NG.NW2_EPG0_SWO_R48_BCF.W)

ENV necessárias (já configuradas como secrets no GitHub):
 - EIA_API_KEY
 - EIA_PETROLEUM_CRUDE_SERIES_ID      (ex: PET.WCESTUS1.W)
 - EIA_PETROLEUM_PRODUCTS_SERIES_ID   (ex: PET.WTTSTUS1.W)
 - EIA_GAS_STORAGE_SERIES_ID          (ex: NG.NW2_EPG0_SWO_R48_BCF.W)
"""

import os
import sys
from datetime import datetime

import pandas as pd
import requests


API_KEY = os.getenv("EIA_API_KEY")
CRUDE_SERIES = os.getenv("EIA_PETROLEUM_CRUDE_SERIES_ID")
PRODUCTS_SERIES = os.getenv("EIA_PETROLEUM_PRODUCTS_SERIES_ID")
GAS_SERIES = os.getenv("EIA_GAS_STORAGE_SERIES_ID")


def _check_env() -> None:
    missing = []
    if not API_KEY:
        missing.append("EIA_API_KEY")
    if not CRUDE_SERIES:
        missing.append("EIA_PETROLEUM_CRUDE_SERIES_ID")
    if not PRODUCTS_SERIES:
        missing.append("EIA_PETROLEUM_PRODUCTS_SERIES_ID")
    if not GAS_SERIES:
        missing.append("EIA_GAS_STORAGE_SERIES_ID")

    if missing:
        print(
            "[EIA] ERROR: missing environment variables: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        sys.exit(2)


def fetch_series(series_id: str) -> dict:
    """Faz o GET na API da EIA para um series_id específico, com logs de debug."""
    if not series_id:
        print(
            "[EIA] ERROR: series_id vazio (env não carregada corretamente).",
            file=sys.stderr,
        )
        sys.exit(2)

    url = f"https://api.eia.gov/series/?api_key={API_KEY}&series_id={series_id}"
    # Log de debug – o GitHub Actions mascara valores de secrets automaticamente.
    print(f"[EIA] Fetching series_id={series_id}", flush=True)

    try:
        r = requests.get(url, timeout=30)
    except Exception as exc:
        print(f"[EIA] Request error for series_id={series_id}: {exc}", file=sys.stderr)
        raise

    if r.status_code != 200:
        print(
            f"[EIA] HTTP {r.status_code} para series_id={series_id}",
            file=sys.stderr,
        )
        # Mostra apenas um trecho da resposta para ajudar no debug
        snippet = r.text[:400].replace("\n", " ")
        print(f"[EIA] Response snippet: {snippet}", file=sys.stderr)

    r.raise_for_status()
    return r.json()


def parse_series_to_df(j: dict) -> pd.DataFrame:
    """Converte o JSON da EIA (series) em DataFrame normalizado."""
    series_list = j.get("series", [])
    if not series_list:
        return pd.DataFrame()

    s0 = series_list[0]
    rows = []

    for entry in s0.get("data", []):
        # formato típico: [date, value]
        date_raw, value = entry[0], entry[1]

        date = None
        for fmt in ("%Y%m%d", "%Y%m", "%Y-%m-%d", "%Y-%m"):
            try:
                date = datetime.strptime(str(date_raw), fmt).date()
                break
            except Exception:
                continue

        if date is None:
            # fallback string
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
    _check_env()

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
