import os
import json
import argparse
import requests
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Variáveis de ambiente (vindas do GitHub Actions)
# ------------------------------------------------------------------
FRED_API_KEY = os.getenv("FRED_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # pode não ser usado ainda

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_ENERGY = os.getenv("TELEGRAM_CHAT_ID_ENERGY")

if FRED_API_KEY is None:
    raise RuntimeError("FRED_API_KEY não encontrado nas variáveis de ambiente.")

if TELEGRAM_BOT_TOKEN is None or TELEGRAM_CHAT_ID_ENERGY is None:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID_ENERGY não configurados."
    )

# ------------------------------------------------------------------
# Telegram: envio de texto
# ------------------------------------------------------------------
def telegram_send_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID_ENERGY,
        "text": text,
        "parse_mode": "Markdown",
    }
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        print("Falha ao enviar mensagem para Telegram:", r.text)


# ------------------------------------------------------------------
# Telegram: envio de documento JSON
# ------------------------------------------------------------------
def telegram_send_document(filepath: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(filepath, "rb") as doc:
        files = {"document": doc}
        data = {"chat_id": TELEGRAM_CHAT_ID_ENERGY}
        r = requests.post(url, data=data, files=files)
        if r.status_code != 200:
            print("Falha ao enviar documento:", r.text)


# ------------------------------------------------------------------
# Coleta de preços do FRED — Série Coal
# ------------------------------------------------------------------
FRED_SERIES_ID = "PCCOALUSDM"  # preço do carvão USD/ton


def get_fred_series():
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": FRED_SERIES_ID,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": (datetime.utcnow() - timedelta(days=60)).strftime(
            "%Y-%m-%d"
        ),
    }

    r = requests.get(url, params=params)
    data = r.json()

    if "observations" not in data:
        raise RuntimeError(f"Erro retornado pelo FRED: {data}")

    obs = [o for o in data["observations"] if o["value"] not in ("", ".")]
    return obs


# ------------------------------------------------------------------
# Monta relatório
# ------------------------------------------------------------------
def build_markdown(obs):
    last = obs[-1]
    price = float(last["value"])
    date = last["date"]

    md = f"""
# 🏭 Coal — Relatório Diário

**Preço mais recente:** *${price:,.2f}*  
**Data:** {date}

---

A cotação do carvão reflete variações ligadas à demanda industrial global, à logística de transporte marítimo
e às mudanças na matriz energética mundial.

Este relatório é gerado automaticamente.
"""
    return md.strip(), price


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    print("🟦 Coletando dados...")
    obs = get_fred_series()

    markdown, price = build_markdown(obs)

    result = {
        "series_id": FRED_SERIES_ID,
        "last_price": price,
        "last_date": obs[-1]["date"],
        "generated_at": datetime.utcnow().isoformat(),
        "preview": args.preview,
        "markdown": markdown,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"🟧 JSON salvo em {args.out}")

    title = "📘 Coal — Relatório Diário (Preview)" if args.preview else "📘 Coal — Relatório Diário"

    print("📨 Enviando relatório...")
    telegram_send_message(title)
    telegram_send_message(markdown)
    telegram_send_document(args.out)

    print("✔ Relatório enviado!")


if __name__ == "__main__":
    main()
