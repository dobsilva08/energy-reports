import os
import json
import argparse
import requests
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Variáveis de ambiente (vindas do GitHub Actions)
# ------------------------------------------------------------------
FRED_API_KEY = os.getenv("FRED_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # reservado para uso futuro

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
# Série válida de carvão (Producer Price Index: Coal, índice 1982=100)
FRED_SERIES_ID = "WPU051"


def get_fred_series():
    """
    Busca observações da série do FRED e garante que exista dado válido.
    Levanta RuntimeError com mensagem descritiva se algo vier vazio/errado.
    """
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": FRED_SERIES_ID,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        # usa 5 anos para garantir dados suficientes
        "observation_start": (datetime.utcnow() - timedelta(days=5 * 365)).strftime(
            "%Y-%m-%d"
        ),
    }

    r = requests.get(url, params=params)
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Resposta inválida do FRED: status={r.status_code}, texto={r.text}")

    if "observations" not in data:
        raise RuntimeError(f"Erro retornado pelo FRED (sem 'observations'): {data}")

    obs_list = data["observations"]

    if not obs_list:
        raise RuntimeError(f"Nenhuma observação retornada para a série {FRED_SERIES_ID}.")

    # Filtra apenas valores válidos
    valid_obs = [o for o in obs_list if o.get("value") not in ("", ".", None)]

    if not valid_obs:
        raise RuntimeError(
            f"Todas as observações estão vazias/sem valor para a série {FRED_SERIES_ID}."
        )

    return valid_obs


# ------------------------------------------------------------------
# Monta relatório
# ------------------------------------------------------------------
def build_markdown(obs):
    last = obs[-1]
    value = float(last["value"])
    date = last["date"]

    md = f"""
# 🏭 Coal — Relatório Diário

**Índice mais recente (PPI – Coal):** *{value:,.2f}*  
**Data da última observação:** {date}

---

Este índice representa o *Producer Price Index* (PPI) para carvão, medindo a variação
dos preços ao produtor do setor de carvão nos Estados Unidos (base 1982=100).

Movimentos nesse índice refletem:
- Mudanças na demanda industrial por carvão;
- Custos de produção e transporte;
- Substituição por outras fontes de energia e políticas de transição energética.

Este relatório é gerado automaticamente como parte da rotina diária de energia.
"""
    return md.strip(), value


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Caminho do arquivo JSON de saída")
    parser.add_argument("--preview", action="store_true", help="Roda em modo de teste")
    args = parser.parse_args()

    try:
        print("🟦 Coletando dados...")
        obs = get_fred_series()

        print("🟩 Construindo relatório...")
        markdown, value = build_markdown(obs)

        result = {
            "series_id": FRED_SERIES_ID,
            "last_value": value,
            "last_date": obs[-1]["date"],
            "generated_at": datetime.utcnow().isoformat(),
            "preview": args.preview,
            "markdown": markdown,
        }

        # Salva JSON
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"🟧 JSON salvo em {args.out}")

        title = (
            "📘 Coal — Relatório Diário (Preview)"
            if args.preview
            else "📘 Coal — Relatório Diário"
        )

        print("📨 Enviando relatório para o Telegram...")
        telegram_send_message(title)
        telegram_send_message(markdown)
        telegram_send_document(args.out)

        print("✔ Relatório enviado!")

    except Exception as e:
        # Loga no console para o GitHub Actions
        print(f"❌ Erro ao gerar relatório de Coal: {e}")
        # Opcional: avisar no Telegram também
        try:
            telegram_send_message(f"❌ Erro ao gerar relatório de Coal:\n`{e}`")
        except Exception as e2:
            print("Falha ao enviar mensagem de erro para o Telegram:", e2)
        # Propaga o erro para o job marcar como falho
        raise


if __name__ == "__main__":
    main()
