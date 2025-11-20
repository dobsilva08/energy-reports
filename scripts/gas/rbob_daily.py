#!/usr/bin/env python3
"""
Baixa preços diários de RBOB (gasolina) usando a API do FRED
e salva em CSV para uso nos relatórios de energia.

Por padrão usa a série:
  - DRGASLA = Reformulated Gasoline Blendstock for Oxygenate Blending (RBOB)
              Prices: Regular Gasoline: Los Angeles (Daily)

Requisitos:
  - Variável de ambiente FRED_API_KEY configurada (já existe no repo).
  - requests, pandas instalados (já estão no requirements).

Exemplo de uso:
  python scripts/gas/rbob_daily.py --out /tmp/rbob_daily.csv

Opcional:
  python scripts/gas/rbob_daily.py --out /tmp/rbob_daily.csv --series-id DRGASLA
"""

import argparse
import os
from datetime import datetime
import requests
import pandas as pd


FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_rbob_from_fred(
    api_key: str,
    series_id: str = "DRGASLA",
    observation_start: str = "2003-01-01",
) -> pd.DataFrame:
    """
    Busca a série de RBOB no FRED e devolve um DataFrame com:
      - date (datetime64[ns])
      - price (float)
      - source (str)
    """

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start,
        "frequency": "d",  # diário
    }

    resp = requests.get(FRED_BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    observations = data.get("observations", [])
    if not observations:
        raise RuntimeError(f"Nenhuma observação retornada para série {series_id} no FRED.")

    rows = []
    for obs in observations:
        date_str = obs.get("date")
        value_str = obs.get("value")

        # FRED usa "." quando não há valor
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

    if not rows:
        raise RuntimeError(f"Nenhum valor numérico válido encontrado para série {series_id}.")

    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Baixa preços diários de RBOB (gasolina) via FRED.")
    parser.add_argument(
        "--out",
        required=True,
        help="Caminho de saída do CSV (ex: /tmp/rbob_daily.csv)",
    )
    parser.add_argument(
        "--series-id",
        default=os.environ.get("RBOB_FRED_SERIES_ID", "DRGASLA"),
        help="ID da série no FRED (default: DRGASLA ou valor de RBOB_FRED_SERIES_ID).",
    )
    parser.add_argument(
        "--start",
        default="2003-01-01",
        help="Data inicial (YYYY-MM-DD) para baixar a série (default: 2003-01-01).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FRED_API_KEY não encontrado nas variáveis de ambiente. "
            "Configure o secret FRED_API_KEY no GitHub e exporte no workflow."
        )

    df = fetch_rbob_from_fred(
        api_key=api_key,
        series_id=args.series_id,
        observation_start=args.start,
    )

    # Garante diretório de saída
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    df.to_csv(out_path, index=False)
    print(f"[RBOB] CSV salvo em: {out_path}")
    print(f"[RBOB] Linhas: {len(df)} | Período: {df['date'].min()} → {df['date'].max()}")


if __name__ == "__main__":
    main()
