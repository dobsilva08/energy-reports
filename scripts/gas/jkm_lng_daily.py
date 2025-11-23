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
# Relatório — Template em tópicos (sem IA)
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

    # Narrativa dinâmica conforme a tendência
    if trend == "alta":
        comentario_curto_prazo = (
            "Pressão altista no curto prazo, refletindo demanda firme por LNG no mercado asiático "
            "ou ajustes na oferta global."
        )
        interpretacao_linha_1 = (
            "JKM LNG em alta, sugerindo ambiente de preços mais apertados para importadores de gás na Ásia."
        )
    elif trend == "queda":
        comentario_curto_prazo = (
            "Pressão baixista no curto prazo, com oferta mais confortável ou demanda temporariamente mais fraca."
        )
        interpretacao_linha_1 = (
            "JKM LNG em queda, indicando alívio parcial nos custos de importação de gás para a Ásia."
        )
    else:
        comentario_curto_prazo = (
            "Curto prazo marcado por relativa estabilidade, com oscilações ligadas a clima, logística "
            "e ajustes marginais de oferta e demanda."
        )
        interpretacao_linha_1 = (
            "JKM LNG em patamar estável, sinalizando balanço relativamente equilibrado entre oferta e demanda."
        )

    interpretacao_linha_2 = (
        "Importadores asiáticos seguem sensíveis a choques de preço no JKM, com impacto direto no custo de "
        "geração elétrica e em contratos indexados ao spot."
    )

    medio_prazo = (
        "No médio prazo, a trajetória do JKM LNG depende da expansão de terminais de liquefação, "
        "contratos de longo prazo, substituição entre gás e outras fontes (carvão, renováveis) e "
        "da dinâmica macroeconômica nas principais economias asiáticas."
    )

    sinal = "+" if delta >= 0 else "-"

    # Cabeçalho
    report = f"""🌏 GNL Ásia — Relatório Diário (JKM LNG) — {today} — Diário</b>

<b>Relatório Diário — Preço spot JKM LNG (PNGASJPUSDM)</b>

<b>1) Preço spot JKM LNG</b>
• Último valor: <b>{last:.2f} USD/MMBtu</b>
• Data da última observação: {last_date}
"""

    # Se tiver leitura anterior, adiciona
    if prev is not None:
        report += (
            f"• Leitura anterior: {prev:.2f} USD/MMBtu ({prev_date})\n"
            f"• Variação diária: {sinal}{abs(delta):.2f} USD/MMBtu "
            f"({sinal}{abs(pct):.2f}%)\n"
        )

    # Demais tópicos
    report += f"""
<b>2) Estrutura de mercado e spreads</b>
• O JKM é referência para precificação de LNG no mercado asiático, com spreads em relação a Henry Hub, TTF
  e outros hubs indicando competitividade relativa das regiões.

<b>3) Oferta global de LNG</b>
• A oferta depende de projetos de liquefação, disponibilidade de shipping (navios de LNG) e eventuais
  interrupções operacionais em plantas produtoras.

<b>4) Demanda asiática</b>
• A demanda é guiada por geração termoelétrica, consumo industrial e clima (ondas de frio ou calor),
  principalmente em economias como Japão, Coreia do Sul e China.

<b>5) Relação com TTF, Henry Hub e outros hubs</b>
• Diferenças de preço entre JKM, TTF (Europa) e Henry Hub (EUA) sinalizam incentivos de arbitragem via LNG,
  redirecionando cargas entre continentes.

<b>6) FX, shipping e custos logísticos</b>
• Custos de frete marítimo, disponibilidade de navios e condições de câmbio impactam o preço efetivo
  pago pelos importadores de LNG.

<b>7) Geopolítica e riscos</b>
• Tensões em regiões produtoras, disputas de rotas marítimas e sanções podem afetar a disponibilidade de
  gás e o fluxo de cargas para a Ásia.

<b>8) Notas de pesquisa e instituições</b>
• Relatórios de agências de energia, bancos e casas de análise monitoram expansão de capacidade de LNG,
  contratos de longo prazo e transição energética na região.

<b>9) Interpretação executiva</b>
• {interpretacao_linha_1}
• {interpretacao_linha_2}

<b>10) Conclusão (curto e médio prazo)</b>
• Curto prazo: {comentario_curto_prazo}
• Médio prazo: {medio_prazo}
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
