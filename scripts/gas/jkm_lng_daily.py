import os
import json
import argparse
import requests
import time
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Variáveis de ambiente
# ------------------------------------------------------------------
FRED_API_KEY = os.getenv("FRED_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_ENERGY = os.getenv("TELEGRAM_CHAT_ID_ENERGY")

if FRED_API_KEY is None:
    raise RuntimeError("FRED_API_KEY não encontrado nas variáveis de ambiente. Configure o secret FRED_API_KEY no GitHub.")
if TELEGRAM_BOT_TOKEN is None or TELEGRAM_CHAT_ID_ENERGY is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID_ENERGY não configurados.")


# ------------------------------------------------------------------
# Telegram
# ------------------------------------------------------------------
def telegram_send_message(text: str) -> None:
    """Envia mensagem no Telegram usando HTML."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID_ENERGY,
        "text": text,
        "parse_mode": "HTML",
    }
    r = requests.post(url, data=payload)
    try:
        data = r.json()
        if not data.get("ok", False):
            print("Erro ao enviar mensagem ao Telegram:", data)
    except Exception:
        print("Resposta inesperada do Telegram:", r.text)


# ------------------------------------------------------------------
# FRED — JKM LNG (Japan LNG Import Price)
# Série: PNGASJPUSDM
# ------------------------------------------------------------------
FRED_SERIES_ID = "PNGASJPUSDM"


def get_fred_series():
    """Baixa a série PNGASJPUSDM do FRED."""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": FRED_SERIES_ID,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": (datetime.utcnow() - timedelta(days=365 * 3)).strftime("%Y-%m-%d"),
    }

    r = requests.get(url, params=params)
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Resposta inválida do FRED: {r.text}")

    if "observations" not in data:
        raise RuntimeError(f"Erro no retorno do FRED: {data}")

    obs_list = [o for o in data["observations"] if o.get("value") not in ("", ".", None)]
    if not obs_list:
        raise RuntimeError("Nenhuma observação válida encontrada.")

    return obs_list


def compute_metrics(obs):
    """Calcula últimas métricas da série."""
    last = obs[-1]
    last_value = float(last["value"])
    last_date = last["date"]

    if len(obs) >= 2:
        prev = obs[-2]
        prev_value = float(prev["value"])
        prev_date = prev["date"]
        delta = last_value - prev_value
        pct_change = (delta / prev_value) * 100 if prev_value != 0 else 0
    else:
        prev_value = None
        prev_date = None
        delta = 0
        pct_change = 0

    if pct_change > 1.0:
        trend = "alta"
    elif pct_change < -1.0:
        trend = "queda"
    else:
        trend = "estabilidade"

    return {
        "last_value": last_value,
        "last_date": last_date,
        "prev_value": prev_value,
        "prev_date": prev_date,
        "delta": delta,
        "pct_change": pct_change,
        "trend": trend,
    }


# ------------------------------------------------------------------
# Relatório — Template sem IA
# ------------------------------------------------------------------
def build_report(metrics):
    today = datetime.utcnow().strftime("%Y-%m-%d")

    last = metrics["last_value"]
    last_date = metrics["last_date"]
    prev = metrics["prev_value"]
    prev_date = metrics["prev_date"]
    delta = metrics["delta"]
    pct = metrics["pct_change"]
    trend = metrics["trend"]

    # Ajusta narrativa
    if trend == "alta":
        comentario = "pressão altista no curto prazo no mercado asiático de LNG."
    elif trend == "queda":
        comentario = "pressão baixista no curto prazo, aliviando custos de importadores asiáticos."
    else:
        comentario = "movimento de estabilidade com balanço entre oferta e demanda."

    sinal = "+" if delta >= 0 else "-"

    report = f"""
📊 <b>Gas — JKM LNG — {today} — Diário</b>

<b>1) Preço Spot (JKM LNG)</b>
• Última leitura: <b>{last:.2f} USD/MMBtu</b>
• Data: {last_date}
"""

    if prev is not None:
        report += f"• Anterior: {prev:.2f} USD/MMBtu ({prev_date})\n"
        report += f"• Variação diária: {sinal}{abs(delta):.2f} USD/MMBtu ({sinal}{abs(pct):.2f}%)\n"

    report += f"""
<b>2) Interpretação Executiva</b>
• O mercado apresenta {comentario}

<b>3) Tendências e Drivers</b>
• Clima na Ásia (demanda de geração elétrica)
• Custos logísticos e disponibilidade de navios LNG
• Oferta global de liquefação (EUA, Qatar, Austrália)
• Arbitragem entre JKM, TTF (Europa) e Henry Hub (EUA)

<b>4) Conclusão</b>
• Cenário de curto prazo: {trend}.
"""

    return report.strip()


# ------------------------------------------------------------------
# MAIN — Tempo total incluído no rodapé
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    start = time.time()

    try:
        obs = get_fred_series()
        metrics = compute_metrics(obs)

        html_text = build_report(metrics)

        end = time.time()
        total_time = end - start

        # Rodapé padronizado
        html_text += f"\n\n<i>LLM: piapi · {total_time:.2f}s</i>"

        # Prepara JSON
        result = {
            "series_id": FRED_SERIES_ID,
            "generated_at": datetime.utcnow().isoformat(),
            "preview": args.preview,
            **metrics,
            "html": html_text,
            "provider": "template",
            "llm_used": False,
            "processing_time": total_time,
        }

        # Salva JSON
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Envia Telegram
        telegram_send_message(html_text)

    except Exception as e:
        print("Erro ao gerar relatório:", e)
        raise


if __name__ == "__main__":
    main()
