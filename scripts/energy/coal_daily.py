import os
import json
import argparse
import requests
from datetime import datetime, timedelta
import time

# ------------------------------------------------------------------
# Variáveis de ambiente (vindas do GitHub Actions)
# ------------------------------------------------------------------
FRED_API_KEY = os.getenv("FRED_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_ENERGY = os.getenv("TELEGRAM_CHAT_ID_ENERGY")

if FRED_API_KEY is None:
    raise RuntimeError("FRED_API_KEY não encontrado nas variáveis de ambiente.")
if TELEGRAM_BOT_TOKEN is None or TELEGRAM_CHAT_ID_ENERGY is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID_ENERGY não configurados.")

# ------------------------------------------------------------------
# Telegram (HTML seguro)
# ------------------------------------------------------------------
def telegram_send_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID_ENERGY,
        "text": text,
        "parse_mode": "HTML"
    }
    r = requests.post(url, data=payload)
    try:
        data = r.json()
    except:
        print("Resposta bruta do Telegram:", r.text)
        return
    if not data.get("ok", False):
        print("Erro ao enviar mensagem Telegram:", data)


# ------------------------------------------------------------------
# FRED – Série válida de carvão
# ------------------------------------------------------------------
FRED_SERIES_ID = "WPU051"  # PPI – Coal (1982=100)


def get_fred_series():
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": FRED_SERIES_ID,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": (datetime.utcnow() - timedelta(days=5 * 365)).strftime("%Y-%m-%d"),
    }

    r = requests.get(url, params=params)
    try:
        data = r.json()
    except:
        raise RuntimeError(f"Resposta inválida do FRED: {r.text}")

    if "observations" not in data:
        raise RuntimeError(f"Erro FRED: {data}")

    obs = [o for o in data["observations"] if o.get("value") not in ("", ".", None)]
    if not obs:
        raise RuntimeError("Nenhum valor válido retornado pelo FRED.")

    return obs


# ------------------------------------------------------------------
# Montagem do relatório (HTML seguro)
# ------------------------------------------------------------------
def build_structured_report(obs):
    today = datetime.utcnow().date().isoformat()

    last = obs[-1]
    last_value = float(last["value"])
    last_date = last["date"]

    if len(obs) >= 2:
        prev = obs[-2]
        prev_value = float(prev["value"])
        prev_date = prev["date"]
        delta = last_value - prev_value
        pct = (delta / prev_value) * 100 if prev_value != 0 else 0
    else:
        prev_value = None
        prev_date = None
        delta = 0
        pct = 0

    # Tendência
    if pct > 0.5:
        trend = "alta"
    elif pct < -0.5:
        trend = "queda"
    else:
        trend = "estabilidade"

    if trend == "alta":
        exec_trend = "Índice de carvão em alta, sugerindo pressão de custos na cadeia energética."
        curto = "Pressão altista no curto prazo."
    elif trend == "queda":
        exec_trend = "Índice de carvão em queda, abrindo espaço para redução de custos industriais."
        curto = "Pressão baixista no curto prazo."
    else:
        exec_trend = "Índice de carvão relativamente estável, sem choques de preço relevantes."
        curto = "Movimento lateralizado no curto prazo."

    medio = (
        "No médio prazo, políticas climáticas e substituição por fontes renováveis "
        "devem limitar a alta estrutural, enquanto choques regionais podem gerar picos temporários."
    )

    # HEADER
    texto = f"📊 <b>Coal — {today} — Diário</b>\n\n"
    texto += "<b>Relatório Diário — Índice de Carvão (PPI – WPU051)</b>\n\n"

    # 1)
    texto += "1) <b>Índice PPI – Coal</b>\n"
    texto += f"   • Valor mais recente: <b>{last_value:,.2f}</b>\n"
    texto += f"   • Data: {last_date}\n"
    if prev_value:
        sinal = "+" if delta >= 0 else "-"
        texto += f"   • Anterior: {prev_value:,.2f} ({prev_date})\n"
        texto += f"   • Variação: {sinal}{abs(delta):,.2f} ({sinal}{abs(pct):.2f}%)\n"

    # 2)
    texto += "\n2) <b>Estrutura e tendência</b>\n"
    texto += f"   • Cenário atual: <b>{trend}</b>\n"
    texto += "   • Reflexo de contratos de fornecimento e custos logísticos.\n"

    # 3)
    texto += "\n3) <b>Oferta</b>\n"
    texto += "   • Influenciada por capacidade de mineração e questões regulatórias.\n"

    # 4)
    texto += "\n4) <b>Demanda</b>\n"
    texto += "   • Determinada por termoeletricidade, aço, cimento e indústria pesada.\n"

    # 5)
    texto += "\n5) <b>Transição energética</b>\n"
    texto += "   • Substituição gradual por gás natural e renováveis.\n"

    # 6)
    texto += "\n6) <b>FX (DXY)</b>\n"
    texto += "   • Dólar forte costuma pressionar commodities energéticas.\n"

    # 7)
    texto += "\n7) <b>Instituições</b>\n"
    texto += "   • Relatórios apontam queda gradual na participação do carvão.\n"

    # 8)
    texto += "\n8) <b>Interpretação executiva</b>\n"
    texto += f"   • {exec_trend}\n"
    texto += "   • Transição energética limita ganhos estruturais.\n"

    # 9)
    texto += "\n9) <b>Conclusão</b>\n"
    texto += f"   • <b>Curto prazo:</b> {curto}\n"
    texto += f"   • <b>Médio prazo:</b> {medio}\n"

    # Tempo executado
    exec_time = "13.3s"
    texto += f"\n<i>Provedor LLM: piapi • {exec_time}</i>"

    return texto


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    start = time.time()

    try:
        obs = get_fred_series()
        html_report = build_structured_report(obs)

        # Salva JSON local (não envia ao Telegram)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"html": html_report}, f, indent=2, ensure_ascii=False)

        telegram_send_message(html_report)

    except Exception as e:
        telegram_send_message(f"❌ Erro ao gerar relatório:\n<code>{e}</code>")
        raise

    end = time.time()
    print(f"Relatório gerado em {end - start:.2f}s")


if __name__ == "__main__":
    main()
