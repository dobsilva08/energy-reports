import os
import json
import argparse
import requests
from datetime import datetime, timedelta
import time

# ------------------------------------------------------------------
# Variáveis de ambiente
# ------------------------------------------------------------------
FRED_API_KEY = os.getenv("FRED_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_ENERGY = os.getenv("TELEGRAM_CHAT_ID_ENERGY")

# Chave opcional da PIAPI (modo B – IA opcional)
PIAPI_API_KEY = os.getenv("PIAPI_API_KEY")

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
        "parse_mode": "HTML",
    }
    r = requests.post(url, data=payload)
    try:
        data = r.json()
    except Exception:
        print("Resposta bruta do Telegram:", r.text)
        return

    if not data.get("ok", False):
        print("Erro ao enviar mensagem Telegram:", data)


# ------------------------------------------------------------------
# FRED – Série de carvão (PPI – Coal)
# ------------------------------------------------------------------
FRED_SERIES_ID = "WPU051"  # Producer Price Index – Coal (1982=100)


def get_fred_series():
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": FRED_SERIES_ID,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": (datetime.utcnow() - timedelta(days=5 * 365)).strftime(
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
        raise RuntimeError("Nenhum valor válido retornado pelo FRED para WPU051.")

    return obs_list


# ------------------------------------------------------------------
# Versão TEMPLATE (sem IA) – texto fixo + regras simples
# ------------------------------------------------------------------
def build_structured_report_template(obs):
    today_str = datetime.utcnow().date().isoformat()

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

    # tendência simples
    if pct_change > 0.5:
        trend = "alta"
        exec_trend = (
            "Índice de carvão em alta, sugerindo pressão de custos na cadeia energética."
        )
        curto_prazo = (
            "Pressão altista no curto prazo, refletindo custos maiores e possível "
            "repasse para cadeias intensivas em carvão."
        )
    elif pct_change < -0.5:
        trend = "queda"
        exec_trend = (
            "Índice de carvão em queda, abrindo espaço para redução de custos industriais."
        )
        curto_prazo = (
            "Pressão baixista no curto prazo, indicando alívio parcial de custos "
            "para setores dependentes de carvão."
        )
    else:
        trend = "estabilidade"
        exec_trend = (
            "Índice de carvão relativamente estável, sem choques de preço relevantes no dia."
        )
        curto_prazo = (
            "Movimento mais lateralizado no curto prazo, com mercado ajustando "
            "expectativas entre oferta, demanda e transição energética."
        )

    medio_prazo = (
        "No médio prazo, a combinação de transição energética, políticas climáticas "
        "e competitividade de outras fontes (gás, renováveis) deve limitar a "
        "capacidade de alta estrutural do carvão, ainda que choques de oferta "
        "regionais possam gerar picos temporários de preço."
    )

    # HEADER
    header = (
        f"📊 <b>Coal — {today_str} — Diário</b>\n\n"
        f"<b>Relatório Diário — Índice de Carvão (PPI – WPU051)</b>\n"
    )

    # 1) Índice
    bloco_1 = (
        "\n1) <b>Índice de preços do carvão (PPI – Coal)</b>\n"
        f"   • Índice mais recente: <b>{last_value:,.2f}</b>\n"
        f"   • Data da última observação: {last_date}"
    )
    if prev_value is not None:
        sinal = "+" if delta >= 0 else "-"
        bloco_1 += (
            f"\n   • Leitura anterior: {prev_value:,.2f} ({prev_date})"
            f"\n   • Variação diária: {sinal}{abs(delta):,.2f} pontos "
            f"({sinal}{abs(pct_change):.2f}%)"
        )

    bloco_2 = (
        "\n\n2) <b>Estrutura de preços e tendência</b>\n"
        f"   • A leitura mais recente aponta para um cenário de <b>{trend}</b> "
        "no índice de preços do carvão.\n"
        "   • Movimentos no PPI de carvão tendem a refletir contratos de fornecimento de "
        "médio prazo, custos de extração, transporte e ajustes com grandes consumidores."
    )

    bloco_3 = (
        "\n\n3) <b>Fatores de oferta</b>\n"
        "   • Capacidade de mineração, custos trabalhistas e logística (portos, ferrovias) "
        "são determinantes da oferta.\n"
        "   • Questões regulatórias e ambientais podem restringir projetos de expansão."
    )

    bloco_4 = (
        "\n\n4) <b>Fatores de demanda</b>\n"
        "   • Demanda ligada à geração termoelétrica e à indústria pesada (aço, cimento).\n"
        "   • Ciclos econômicos globais, em especial na Ásia, afetam diretamente o consumo."
    )

    bloco_5 = (
        "\n\n5) <b>Transição energética e substituição</b>\n"
        "   • Descarbonização e maior participação de renováveis reduzem gradualmente "
        "o espaço do carvão na matriz.\n"
        "   • Choques em outras fontes (gás, petróleo) podem gerar movimentos táticos "
        "de volta ao carvão no curto prazo."
    )

    bloco_6 = (
        "\n\n6) <b>FX (DXY) e condições financeiras</b>\n"
        "   • Dólar mais forte tende a pressionar commodities cotadas em USD, "
        "encarecendo a importação de carvão.\n"
        "   • Juros mais altos reduzem investimentos em capacidade e logística."
    )

    bloco_7 = (
        "\n\n7) <b>Notas de pesquisa e instituições</b>\n"
        "   • Agências de energia apontam queda gradual na participação do carvão, "
        "embora ainda partindo de uma base elevada em países em desenvolvimento.\n"
        "   • Revisões de cenário acompanham crescimento global, política climática "
        "e choques de oferta em outras fontes."
    )

    bloco_8 = (
        "\n\n8) <b>Interpretação executiva</b>\n"
        f"   • {exec_trend}\n"
        "   • Custos de geração termoelétrica e indústria pesada seguem sensíveis "
        "ao comportamento do índice.\n"
        "   • Dólar e condições financeiras continuam importantes para o custo global de energia."
    )

    bloco_9 = (
        "\n\n9) <b>Conclusão (curto e médio prazo)</b>\n"
        f"   • <b>Curto prazo:</b> {curto_prazo}\n"
        f"   • <b>Médio prazo:</b> {medio_prazo}"
    )

    bloco_10 = "\n\n<i>Modo: template (sem LLM)</i>"

    html_text = (
        header
        + bloco_1
        + bloco_2
        + bloco_3
        + bloco_4
        + bloco_5
        + bloco_6
        + bloco_7
        + bloco_8
        + bloco_9
        + bloco_10
    ).strip()

    return {
        "html": html_text,
        "last_value": last_value,
        "last_date": last_date,
        "prev_value": prev_value,
        "prev_date": prev_date,
        "delta": delta,
        "pct_change": pct_change,
        "trend": trend,
        "provider": "template",
        "llm_used": False,
    }


# ------------------------------------------------------------------
# (FUTURO) Versão com IA – pronta para integrar PIAPI
# ------------------------------------------------------------------
def build_structured_report_llm(obs):
    """
    Aqui entra a integração REAL com a PIAPI.

    Neste momento, esta função só reusa o template para não quebrar nada.
    Quando você quiser plugar a IA de verdade, usamos PIAPI_API_KEY aqui
    (por exemplo, copiando o padrão que você já tiver no relatório de Oil).

    Retorna o mesmo formato de dict da função de template.
    """
    # TODO: implementar chamada real à PIAPI usando PIAPI_API_KEY
    # Por enquanto, apenas reaproveita o template:
    base = build_structured_report_template(obs)
    base["provider"] = "piapi (placeholder)"
    base["llm_used"] = False
    # opcionalmente mudar o rodapé para indicar placeholder
    base["html"] = base["html"].replace(
        "Modo: template (sem LLM)",
        "Provedor LLM: piapi • (placeholder, sem chamada real)",
    )
    return base


# ------------------------------------------------------------------
# Escolhe entre IA (se disponível) e template
# ------------------------------------------------------------------
def build_structured_report(obs):
    """
    Modo B — IA opcional:

    - Se PIAPI_API_KEY existir:
        tenta usar LLM (build_structured_report_llm).
        se falhar → cai para template.
    - Se não existir:
        usa somente o template.
    """
    if PIAPI_API_KEY:
        try:
            print("PIAPI_API_KEY encontrada — (placeholder) usando caminho LLM...")
            return build_structured_report_llm(obs)
        except Exception as e:
            print("Erro ao usar PIAPI, caindo para template:", e)
            return build_structured_report_template(obs)
    else:
        print("PIAPI_API_KEY não configurada — usando template (sem IA).")
        return build_structured_report_template(obs)


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
        print("🟦 Coletando dados do FRED...")
        obs = get_fred_series()

        print("🟩 Construindo relatório (IA opcional)...")
        report = build_structured_report(obs)
        html_text = report["html"]

        # salva JSON local (metadados + html)
        result = {
            "series_id": FRED_SERIES_ID,
            "generated_at": datetime.utcnow().isoformat(),
            "preview": args.preview,
            **report,
        }

        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"🟧 JSON salvo em {args.out}")

        print("📨 Enviando relatório único para o Telegram...")
        telegram_send_message(html_text)

        end = time.time()
        print(f"✔ Relatório enviado! Tempo total: {end - start:.2f}s")

    except Exception as e:
        print(f"❌ Erro ao gerar relatório de Coal: {e}")
        try:
            telegram_send_message(
                f"❌ Erro ao gerar relatório de Coal:\n<code>{e}</code>"
            )
        except Exception as e2:
            print("Falha ao enviar mensagem de erro para o Telegram:", e2)
        raise


if __name__ == "__main__":
    main()
