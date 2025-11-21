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
    """
    Envia mensagem para o Telegram usando HTML.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID_ENERGY,
        "text": text,
        "parse_mode": "HTML",
    }
    r = requests.post(url, data=payload)
    try:
        data = r.json()
    except Exception:
        print("Resposta bruta do Telegram:", r.text)
        return

    if not data.get("ok", False):
        print("Erro ao enviar mensagem para Telegram:", data)


# ------------------------------------------------------------------
# FRED – JKM LNG (Japan LNG Import Price, US$/MMBtu)
# Série: PNGASJPUSDM
# ------------------------------------------------------------------
FRED_SERIES_ID = "PNGASJPUSDM"


def get_fred_series():
    """
    Busca observações da série PNGASJPUSDM no FRED.
    """
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": FRED_SERIES_ID,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": (datetime.utcnow() - timedelta(days=365 * 3)).strftime(
            "%Y-%m-%d"
        ),
    }

    r = requests.get(url, params=params)
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"Resposta inválida do FRED: {r.text}")

    if "observations" not in data:
        raise RuntimeError(f"Erro FRED (sem 'observations'): {data}")

    obs_list = [
        o for o in data["observations"] if o.get("value") not in ("", ".", None)
    ]
    if not obs_list:
        raise RuntimeError(
            f"Nenhum valor válido retornado para a série {FRED_SERIES_ID}."
        )

    return obs_list


def compute_metrics(obs):
    last = obs[-1]
    last_value = float(last["value"])
    last_date = last["date"]

    if len(obs) >= 2:
        prev = obs[-2]
        prev_value = float(prev["value"])
        prev_date = prev["date"]
        delta = last_value - prev_value
        pct_change = (delta / prev_value) * 100 if prev_value != 0 else 0.0
    else:
        prev_value = None
        prev_date = None
        delta = 0.0
        pct_change = 0.0

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
# Construção do relatório (template, sem IA)
# ------------------------------------------------------------------
def build_report(metrics):
    today_str = datetime.utcnow().date().isoformat()

    last_value = metrics["last_value"]
    last_date = metrics["last_date"]
    prev_value = metrics["prev_value"]
    prev_date = metrics["prev_date"]
    delta = metrics["delta"]
    pct_change = metrics["pct_change"]
    trend = metrics["trend"]

    if trend == "alta":
        curto = (
            "Pressão altista no curto prazo, refletindo demanda firme por LNG no mercado asiático "
            "ou ajustes na oferta global."
        )
        exec_trend = (
            "JKM LNG em alta, sugerindo ambiente de preços mais apertados para importadores de gás na Ásia."
        )
    elif trend == "queda":
        curto = (
            "Pressão baixista no curto prazo, indicando maior conforto de oferta ou demanda mais fraca "
            "na região asiática."
        )
        exec_trend = (
            "JKM LNG em queda, abrindo espaço para alívio de custos em contratos indexados ao preço spot."
        )
    else:
        curto = (
            "Movimento lateral no curto prazo, com o mercado equilibrando drivers de oferta (produção, shipping) "
            "e demanda (clima, geração elétrica, indústria)."
        )
        exec_trend = (
            "JKM LNG relativamente estável, sem choques relevantes de oferta ou demanda no curto prazo."
        )

    medio = (
        "No médio prazo, a evolução do JKM LNG depende da expansão de terminais de liquefação, contratos de longo prazo, "
        "substituição entre gás e outras fontes (carvão, renováveis) e da trajetória macroeconômica na Ásia."
    )

    # Cabeçalho
    texto = f"📊 <b>Gas — JKM LNG — {today_str} — Diário</b>\n\n"
    texto += "<b>Relatório Diário — Preço spot JKM LNG (PNGASJPUSDM)</b>\n\n"

    # 1) Preço JKM
    texto += "1) <b>Preço spot JKM LNG</b>\n"
    texto += f"   • Último valor: <b>{last_value:,.2f} USD/MMBtu</b>\n"
    texto += f"   • Data da última observação: {last_date}\n"
    if prev_value is not None:
        sinal = "+" if delta >= 0 else "-"
        texto += f"   • Leitura anterior: {prev_value:,.2f} USD/MMBtu ({prev_date})\n"
        texto += (
            f"   • Variação diária: {sinal}{abs(delta):,.2f} USD/MMBtu "
            f"({sinal}{abs(pct_change):.2f}%)\n"
        )

    # 2) Estrutura de mercado
    texto += "\n2) <b>Estrutura de mercado e spreads</b>\n"
    texto += (
        "   • O JKM é referência para precificação de LNG no mercado asiático, com spreads em relação a Henry Hub, TTF\n"
        "     e outros hubs indicando competitividade relativa das regiões.\n"
    )

    # 3) Oferta global de LNG
    texto += "\n3) <b>Oferta global de LNG</b>\n"
    texto += (
        "   • A oferta depende de projetos de liquefação, disponibilidade de shipping (navios de LNG) e eventuais\n"
        "     interrupções operacionais em plantas produtoras.\n"
    )

    # 4) Demanda asiática
    texto += "\n4) <b>Demanda asiática</b>\n"
    texto += (
        "   • A demanda é guiada por geração termoelétrica, consumo industrial e clima (ondas de frio ou calor),\n"
        "     principalmente em economias como Japão, Coreia do Sul e China.\n"
    )

    # 5) Relação com hubs europeus e americanos
    texto += "\n5) <b>Relação com TTF, Henry Hub e outros hubs</b>\n"
    texto += (
        "   • Diferenças de preço entre JKM, TTF (Europa) e Henry Hub (EUA) sinalizam incentivos de arbitragem via LNG,\n"
        "     redirecionando cargas entre continentes.\n"
    )

    # 6) FX, shipping e custos logísticos
    texto += "\n6) <b>FX, shipping e custos logísticos</b>\n"
    texto += (
        "   • Custos de frete marítimo, disponibilidade de navios e condições de câmbio impactam o preço efetivo\n"
        "     pago pelos importadores de LNG.\n"
    )

    # 7) Geopolítica e riscos
    texto += "\n7) <b>Geopolítica e riscos</b>\n"
    texto += (
        "   • Tensões em regiões produtoras, disputas de rotas marítimas e sanções podem afetar a disponibilidade de\n"
        "     gás e o fluxo de cargas para a Ásia.\n"
    )

    # 8) Notas de pesquisa e instituições
    texto += "\n8) <b>Notas de pesquisa e instituições</b>\n"
    texto += (
        "   • Relatórios de agências de energia, bancos e casas de análise monitoram expansão de capacidade de LNG,\n"
        "     contratos de longo prazo e transição energética na região.\n"
    )

    # 9) Interpretação executiva
    texto += "\n9) <b>Interpretação executiva</b>\n"
    texto += f"   • {exec_trend}\n"
    texto += (
        "   • Importadores asiáticos seguem sensíveis a choques de preço no JKM, com impacto direto no custo de geração\n"
        "     elétrica e em contratos indexados ao spot.\n"
    )

    # 10) Conclusão
    texto += "\n10) <b>Conclusão (curto e médio prazo)</b>\n"
    texto += f"   • <b>Curto prazo:</b> {curto}\n"
    texto += f"   • <b>Médio prazo:</b> {medio}\n"

    return texto


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Caminho do arquivo JSON de saída")
    parser.add_argument("--preview", action="store_true", help="Roda em modo de teste")
    args = parser.parse_args()

    start = time.time()

    try:
        print("🟦 Coletando dados de JKM LNG no FRED...")
        obs = get_fred_series()
        metrics = compute_metrics(obs)

        print("🟩 Construindo relatório (template)...")
        t_rep_ini = time.time()
        html_text = build_report(metrics)
        t_rep_fim = time.time()
        llm_time = t_rep_fim - t_rep_ini

        # Rodapé no padrão
        html_text += f"\n\n<i>LLM: piapi · {llm_time:.1f}s</i>"

        result = {
            "series_id": FRED_SERIES_ID,
            "generated_at": datetime.utcnow().isoformat(),
            "preview": args.preview,
            **metrics,
            "html": html_text,
            "provider": "template",
            "llm_used": False,
            "llm_time": llm_time,
        }

        out_path = args.out
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"🟧 JSON salvo em {out_path}")

        print("📨 Enviando relatório para o Telegram...")
        telegram_send_message(html_text)

        end = time.time()
        print(f"✔ Relatório de JKM LNG enviado! Tempo total: {end - start:.2f}s")

    except Exception as e:
        print(f"❌ Erro ao gerar relatório de JKM LNG: {e}")
        raise


if __name__ == "__main__":
    main()
