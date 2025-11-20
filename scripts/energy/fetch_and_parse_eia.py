#!/usr/bin/env python3
"""
Busca múltiplas séries semanais da EIA via API v2 (rota /v2/seriesid)
e gera 3 CSVs:

 - /tmp/petroleum_crude.csv        -> estoques comerciais de crude
 - /tmp/petroleum_products.csv     -> estoques de crude + produtos
 - /tmp/gas_storage.csv            -> working gas in storage (Bcf)

ENV necessárias (já configuradas como secrets no GitHub):
 - EIA_API_KEY
 - EIA_PETROLEUM_CRUDE_SERIES_ID      (ex: PET.WCESTUS1.W)
 - EIA_PETROLEUM_PRODUCTS_SERIES_ID   (ex: PET.WTTSTUS1.W)
 - EIA_GAS_STORAGE_SERIES_ID          (ex: NG.NW2_EPG0_SWO_R48_BCF.W)

Obs: usa endpoint de compatibilidade v2:
  https://api.eia.gov/v2/seriesid/{series_id}?api_key=...
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
    """
    Faz o GET na API v2 da EIA para um series_id v1 usando rota /v2/seriesid.
    """
    if not series_id:
        print(
            "[EIA] ERROR: series_id vazio (env não carregada corretamente).",
            file=sys.stderr,
        )
        sys.exit(2)

    # ⚠️ IMPORTANTE: usar API v2 /seriesid/{V1_SERIES_ID}
    url = f"https://api.eia.gov/v2/seriesid/{series_id}?api_key={API_KEY}"

    # GitHub mascara secrets automaticamente no log
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
        snippet = r.text[:400].replace("\n", " ")
        print(f"[EIA] Response snippet: {snippet}", file=sys.stderr)

    r.raise_for_status()
    return r.json()


def parse_series_to_df(j: dict) -> pd.DataFrame:
    """
    Converte o JSON da EIA (API v2 /seriesid) em DataFrame normalizado.

    Estrutura esperada (v2):
      {
        "response": {
          "data": [
            {
              "period": "2024-01-05",
              "value": "123.4",
              ...
            },
            ...
          ],
          "series": [
            {
              "seriesId": "PET.WCESTUS1.W",
              "name": "...",
              ...
            }
          ]
        },
        "request": {...},
        "apiVersion": "2.1.0"
      }
    """

    resp = j.get("response", {})
    data_list = resp.get("data", [])
    series_meta = resp.get("series", [])
    meta = series_meta[0] if series_meta else {}

    series_id = meta.get("seriesId") or meta.get("series_id")
    label = meta.get("name") or meta.get("description") or ""

    rows = []

    for entry in data_list:
        # period é o campo padrão de tempo na v2
        date_raw = entry.get("period") or entry.get("date")

        # converter data; API pode retornar "YYYY", "YYYY-MM", "YYYY-MM-DD", etc
        date = None
        if isinstance(date_raw, str):
            for fmt in ("%Y-%m-%d", "%Y-%m", "%Y%m%d", "%Y%m", "%Y"):
                try:
                    date = datetime.strptime(date_raw, fmt).date()
                    break
                except Exception:
                    continue
        if date is None:
            date = date_raw  # fallback: deixa como string mesmo

        # valor: API v2 costuma retornar em "value" como string
        value_raw = entry.get("value")

        # fallback: se não tiver "value", tenta achar o primeiro numérico
        if value_raw is None:
            for k, v in entry.items():
                if k in ("period", "date"):
                    continue
                # tenta interpretar como float
                try:
                    float(v)
                    value_raw = v
                    break
                except Exception:
                    continue

        value = None
        if value_raw not in (None, ""):
            try:
                value = float(value_raw)
            except Exception:
                # se não der pra converter, deixa como None
                value = None

        rows.append(
            {
                "date": date,
                "value": value,
                "series_id": series_id,
                "label": label,
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
