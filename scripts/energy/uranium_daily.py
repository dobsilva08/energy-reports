#!/usr/bin/env python3
"""
Baixa o preço spot de Urânio (U3O8) usando APENAS o FRED.

Série padrão:
  - URANIUM = Uranium U3O8 Spot Price (US$/lb)

Requisitos:
  - FRED_API_KEY configurada nos secrets do GitHub
  - TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID_ENERGY (para envio opcional)
  - requests, pandas instalados

Saída:
  - CSV com colunas: date, price, source

Uso (local ou no workflow):
  python scripts/energy/uranium_daily.py --out /tmp/uranium_price.csv
"""

import argparse
import os
from datetime import datetime
import requests
import pandas as pd

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_uranium_from_fred(
    api_key: str,
    series_id: str = "URANIUM",
    observation_start: str = "1990-01-01",
) -> pd.DataFrame:
    """
    Busca Uranium U3O8 Spot Price (US$/lb) via FRED.

    Série default:
      - URANIUM
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start,
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

        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        rows.append(
            {
                "date": dt,
                "price": price,
                "source": f"FRED:{series_id}",
            }
        )

    if not rows:
        raise RuntimeError(f"Nenhum valor numérico válido encontrado para série {series_id}.")

    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def send_telegram_message(text: str) -> None:
    """Envia uma mensagem simples para o Telegram (se envs estiverem configuradas)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID_ENERGY") or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[URANIUM/TELEGRAM] TELEGRAM_BOT_TOKEN ou CHAT_ID não configurados. Pulando envio.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print("[URANIUM/TELEGRAM] Mensagem enviada com sucesso.")
    except Exception as e:
        print(f"[URANIUM/TELEGRAM] Falha ao enviar mensagem: {e}")


def main():
    parser = argparse.ArgumentParser(description="Baixa preço spot de Urânio (U3O8) via FRED.")
    parser.add_argument(
        "--out",
        required=True,
        help="Caminho do CSV de saída (ex: /tmp/uranium_price.csv)",
    )
    parser.add_argument(
        "--series-id",
        default=os.environ.get("URANIUM_FRED_SERIES_ID", "URANIUM"),
        help="ID da série no FRED (default: URANIUM).",
    )
    parser.add_argument(
        "--start",
        default="1990-01-01",
        help="Data inicial para FRED (YYYY-MM-DD, default: 1990-01-01).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FRED_API_KEY não encontrado nas variáveis de ambiente. "
            "Configure o secret FRED_API_KEY no GitHub."
        )

    df = fetch_uranium_from_fred(
        api_key=api_key,
        series_id=args.series_id,
        observation_start=args.start,
    )

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    df.to_csv(out_path, index=False)
    print(f"[URANIUM/FRED] CSV salvo em {out_path}")
    print(f"[URANIUM/FRED] Linhas: {len(df)} — Período {df['date'].min()} → {df['date'].max()}")

    # ---- Enviar resumo pro Telegram ----
    last_row = df.iloc[-1]
    last_date = last_row["date"]
    last_price = last_row["price"]

    msg = (
        "📊 *Uranium — Relatório Diário*\n\n"
        f"Último preço: *{last_price:.2f} USD/lb* em *{last_date}*.\n\n"
        f"Período baixado: {df['date'].min()} → {df['date'].max()}\n"
        f"Total de observações: {len(df)}"
    )
    send_telegram_message(msg)


if __name__ == "__main__":
    main()
