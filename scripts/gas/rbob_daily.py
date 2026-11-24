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
    raise RuntimeError("FRED_API_KEY não encontrado nas variáveis de ambiente.")
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
    r = requests.post(url, data=payload, timeout=30)\n    r.raise_for_status()
    try:
        data = r.json()
    except Exception:
        print("Resposta bruta do Telegram:", r.text)
        return

    if not data.get("ok", False):
        print("Erro ao enviar mensagem para Telegram:", data)


# ------------------------------------------------------------------
# FRED – RBOB (Reformulated Gasoline Blendstock for Oxygenate Blending)
# Série diária: DRGASLA (Los Angeles, Dollars/gal, daily)
# ------------------------------------------------------------------
FRED_SERIES_ID = "DRGASLA"


def get_fred_series():
    """
    Busca observações da série DRGASLA no FRED.
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

    if pct_change > 0.75:
        trend = "alta"
    elif pct_change < -0.75:
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
            "Pressão altista no curto prazo, com provável repasse de preços para a cadeia "
            "de distribuição e varejo de combustíveis."
        )
        exec_trend = (
            "RBOB em alta, sugerindo pressão de preços na gasolina e spreads mais fortes "
            "em relação ao crude."
        )
    elif trend == "queda":
        curto = (
            "Pressão baixista no curto prazo, indicando algum alívio sobre margens de "
            "refino e custos de transporte."
        )
        exec_trend = (
            "RBOB em queda, abrindo espaço para flexibilização de preços ao consumidor "
            "onde impostos permitem."
        )
    else:
        curto = (
            "Movimento mais lateralizado no curto prazo, com o mercado calibrando "
            "expectativas entre demanda de mobilidade e oferta de refinarias."
        )
        exec_trend = (
            "RBOB relativamente estável, sem choques relevantes de oferta ou demanda "
            "no horizonte imediato."
        )

    medio = (
        "No médio prazo, a evolução da demanda por mobilidade, políticas de biocombustíveis "
        "e eficiência de frota devem modular o balanço entre oferta de RBOB e consumo. "
        "Choques em petróleo bruto e spreads de refino podem alterar esse quadro rapidamente."
    )

    # Cabeçalho
    texto = f"⛽ <b>Gasolina RBOB — Relatório Diário — {today_str} — Diário</b>\n\n"
    texto += "<b>Relatório Diário — Preço RBOB (DRGASLA — Los Angeles)</b>\n\n"

    # 1) Preço RBOB
    texto += "1) <b>Preço spot RBOB (Los Angeles)</b>\n"
    texto += f"   • Último valor: <b>{last_value:,.4f} USD/gal</b>\n"
    texto += f"   • Data da última observação: {last_date}\n"
    if prev_value is not None:
        sinal = "+" if delta >= 0 else "-"
        texto += f"   • Leitura anterior: {prev_value:,.4f} USD/gal ({prev_date})\n"
        texto += (
            f"   • Variação diária: {sinal}{abs(delta):,.4f} USD/gal "
            f"({sinal}{abs(pct_change):.2f}%)\n"
        )

    # 2) Estrutura da curva e spreads
    texto += "\n2) <b>Curva e spreads</b>\n"
    texto += (
        "   • O RBOB é referência para contratos futuros de gasolina nos EUA, com spreads\n"
        "     em relação ao WTI e a outras frações refinadas indicando expectativas de\n"
        "     margem de refino (crack spread).\n"
    )

    # 3) Estoques e refino
    texto += "\n3) <b>Estoques e atividade de refino</b>\n"
    texto += (
        "   • Níveis de estoque de gasolina, utilização de refinarias e paradas para\n"
        "     manutenção são fatores centrais para a dinâmica de curto prazo do RBOB.\n"
        "   • Relatórios semanais da EIA ajudam a calibrar esse balanço entre oferta e demanda.\n"
    )

    # 4) Demanda de mobilidade
    texto += "\n4) <b>Demanda de mobilidade</b>\n"
    texto += (
        "   • A demanda é fortemente ligada à quilometragem rodada, deslocamentos urbanos\n"
        "     e atividade logística.\n"
        "   • Sazonalidade (verão nos EUA, feriados prolongados) tende a influenciar o\n"
        "     consumo de gasolina e, consequentemente, o RBOB.\n"
    )

    # 5) Relação com petróleo bruto e crack spread
    texto += "\n5) <b>Relação com petróleo bruto e crack spread</b>\n"
    texto += (
        "   • O RBOB costuma seguir a tendência do WTI/Brent, mas também reflete gargalos\n"
        "     específicos de refino e distribuição.\n"
        "   • Crack spreads mais altos indicam margens melhores para refinarias; spreads\n"
        "     comprimidos sugerem pressão nas margens.\n"
    )

    # 6) FX, juros e condições financeiras
    texto += "\n6) <b>FX (DXY), juros e condições financeiras</b>\n"
    texto += (
        "   • Um dólar mais forte tende a pressionar preços de combustíveis para países\n"
        "     importadores, enquanto movimentos em juros afetam o apetite por risco em\n"
        "     commodities energéticas.\n"
    )

    # 7) Geopolítica e riscos
    texto += "\n7) <b>Geopolítica e riscos</b>\n"
    texto += (
        "   • Tensões em regiões produtoras, riscos de oferta em refinarias costeiras e\n"
        "     eventos climáticos (furacões no Golfo do México, por exemplo) podem gerar\n"
        "     volatilidade adicional nos preços do RBOB.\n"
    )

    # 8) Notas de pesquisa e instituições
    texto += "\n8) <b>Notas de pesquisa e instituições</b>\n"
    texto += (
        "   • Relatórios de bancos, agências de energia e casas de análise monitoram o\n"
        "     balanço entre demanda por mobilidade, margens de refino e transição energética.\n"
        "   • Revisões de cenário costumam acompanhar dados mais recentes de consumo e\n"
        "     estoques, além da trajetória macroeconômica global.\n"
    )

    # 9) Interpretação executiva
    texto += "\n9) <b>Interpretação executiva</b>\n"
    texto += f"   • {exec_trend}\n"
    texto += (
        "   • A dinâmica de RBOB permanece sensível a dados semanais de estoques, spreads\n"
        "     de refino e notícias geopolíticas.\n"
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
        print("🟦 Coletando dados de RBOB no FRED...")
        obs = get_fred_series()
        metrics = compute_metrics(obs)

        print("🟩 Construindo relatório (template)...")
        t_rep_ini = time.time()
        html_text = build_report(metrics)
        t_rep_fim = time.time()
        llm_time = t_rep_fim - t_rep_ini

        # adiciona rodapé no formato pedido
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

        # salva JSON
        out_path = args.out
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"🟧 JSON salvo em {out_path}")

        # envio único
        print("📨 Enviando relatório para o Telegram...")
        telegram_send_message(html_text)

        end = time.time()
        print(f"✔ Relatório de RBOB enviado! Tempo total: {end - start:.2f}s")

    except Exception as e:
        print(f"❌ Erro ao gerar relatório de RBOB: {e}")
        raise


if __name__ == "__main__":
    main()
