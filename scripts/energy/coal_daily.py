import os
import json
import argparse
import requests
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Variáveis de ambiente (vindas do GitHub Actions)
# ------------------------------------------------------------------
FRED_API_KEY = os.getenv("FRED_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # reservado p/ uso futuro

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_ENERGY = os.getenv("TELEGRAM_CHAT_ID_ENERGY")

if FRED_API_KEY is None:
    raise RuntimeError("FRED_API_KEY não encontrado nas variáveis de ambiente.")

if TELEGRAM_BOT_TOKEN is None or TELEGRAM_CHAT_ID_ENERGY is None:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID_ENERGY não configurados."
    )

# ------------------------------------------------------------------
# Telegram
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


def telegram_send_document(filepath: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(filepath, "rb") as doc:
        files = {"document": doc}
        data = {"chat_id": TELEGRAM_CHAT_ID_ENERGY}
        r = requests.post(url, data=data, files=files)
        if r.status_code != 200:
            print("Falha ao enviar documento:", r.text)


# ------------------------------------------------------------------
# FRED — Série de carvão
# ------------------------------------------------------------------
# Producer Price Index by Commodity: Fuels and Related Products and Power: Coal
# (índice 1982=100)
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
        # janela grande para sempre ter histórico
        "observation_start": (datetime.utcnow() - timedelta(days=5 * 365)).strftime(
            "%Y-%m-%d"
        ),
    }

    r = requests.get(url, params=params)
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(
            f"Resposta inválida do FRED: status={r.status_code}, texto={r.text}"
        )

    if "observations" not in data:
        raise RuntimeError(f"Erro retornado pelo FRED (sem 'observations'): {data}")

    obs_list = data["observations"]
    if not obs_list:
        raise RuntimeError(f"Nenhuma observação retornada para a série {FRED_SERIES_ID}.")

    valid_obs = [o for o in obs_list if o.get("value") not in ("", ".", None)]
    if not valid_obs:
        raise RuntimeError(
            f"Todas as observações estão vazias/sem valor para a série {FRED_SERIES_ID}."
        )

    return valid_obs


# ------------------------------------------------------------------
# Monta relatório em formato “WTI+Brent”
# ------------------------------------------------------------------
def build_structured_report(obs):
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
    elif pct_change < -0.5:
        trend = "queda"
    else:
        trend = "estabilidade"

    # interpretação simples baseada em tendência
    if trend == "alta":
        curto_prazo = (
            "Pressão altista no curto prazo, refletindo custos maiores e possível "
            "repasse para cadeias intensivas em carvão."
        )
        exec_bullet_trend = "Índice de carvão em alta, sugerindo pressão de custos na cadeia energética."
    elif trend == "queda":
        curto_prazo = (
            "Pressão baixista no curto prazo, indicando alívio parcial de custos "
            "para setores dependentes de carvão."
        )
        exec_bullet_trend = "Índice de carvão em queda, abrindo espaço para redução de custos industriais."
    else:
        curto_prazo = (
            "Movimento mais lateralizado no curto prazo, com mercado ajustando "
            "expectativas entre oferta, demanda e transição energética."
        )
        exec_bullet_trend = "Índice de carvão relativamente estável, sem choques de preço relevantes no dia."

    medio_prazo = (
        "No médio prazo, a combinação de transição energética, políticas climáticas "
        "e competitividade de outras fontes (gás, renováveis) deve limitar a "
        "capacidade de alta estrutural do carvão, ainda que choques de oferta "
        "regionais possam gerar picos temporários de preço."
    )

    # header + corpo
    header = f"📊 Coal — {today_str} — Diário\n\n**Relatório Diário — Índice de Carvão (PPI – WPU051)**\n"

    bloco_1 = f"""
1) **Índice de preços do carvão (PPI – Coal)**
   - Índice mais recente: {last_value:,.2f}
   - Data da última observação: {last_date}"""
    if prev_value is not None:
        sinal = "+" if delta >= 0 else "-"
        bloco_1 += f"""
   - Leitura anterior: {prev_value:,.2f} ({prev_date})
   - Variação diária: {sinal}{abs(delta):,.2f} pontos ({sinal}{abs(pct_change):.2f}%)"""

    bloco_2 = f"""
2) **Estrutura de preços e tendência**
   - A leitura mais recente aponta para um cenário de **{trend}** no índice de preços do carvão.
   - Movimentos no PPI de carvão tendem a refletir contratos de fornecimento de médio prazo,
     custos de extração, transporte ferroviário e marítimo, além de ajustes contratuais
     com grandes consumidores industriais."""

    bloco_3 = """
3) **Fatores de oferta**
   - A oferta de carvão é influenciada por capacidade de mineração, custos trabalhistas,
     disponibilidade logística (portos, ferrovias) e eventuais interrupções em regiões
     produtoras-chave.
   - Questões regulatórias e ambientais podem restringir projetos de expansão, criando
     assimetrias entre demanda e oferta em determinados períodos."""

    bloco_4 = """
4) **Fatores de demanda**
   - A demanda está ligada principalmente à geração termoelétrica e à indústria pesada
     (aço, cimento, química).
   - Ciclos econômicos globais, em especial na Ásia, costumam ter impacto direto na
     utilização do carvão como fonte de energia de base."""

    bloco_5 = """
5) **Transição energética e substituição**
   - A aceleração da agenda de descarbonização, com maior participação de renováveis
     e gás natural, pressiona estruturalmente o papel do carvão na matriz energética.
   - Ao mesmo tempo, choques em outras fontes (como gás ou petróleo) podem gerar
     movimentos táticos de volta ao carvão em alguns países."""

    bloco_6 = """
6) **FX (DXY) e condições financeiras**
   - Um dólar mais forte tende a pressionar commodities cotadas em USD, encarecendo
     a importação de carvão para economias emergentes.
   - Condições financeiras mais apertadas (juros mais altos) podem reduzir investimentos
     em expansão de capacidade e logística."""

    bloco_7 = """
7) **Notas de pesquisa e instituições**
   - Relatórios de instituições multilaterais e agências de energia apontam que a
     participação do carvão na matriz tende a cair gradualmente, mas ainda parte
     de uma base elevada em países em desenvolvimento.
   - Revisões de cenário costumam acompanhar mudanças em crescimento global,
     política climática e choques de oferta em outras fontes de energia."""

    bloco_8 = f"""
8) **Interpretação executiva (bullet points)**
   - {exec_bullet_trend}
   - Custos de geração termoelétrica e indústria pesada seguem sensíveis ao comportamento do índice.
   - Transição energética limita a alta estrutural, mas choques de curto prazo ainda podem ser relevantes.
   - Dólar e condições financeiras continuam importantes para o custo global de energia."""

    bloco_9 = f"""
9) **Conclusão (curto e médio prazo)**
   - **Curto prazo:** {curto_prazo}
   - **Médio prazo:** {medio_prazo}"""

    # Se quiser, pode registrar aqui qual LLM/engine gerou (mesmo sendo template)
    bloco_10 = "\n\nLLM: template_coal · deterministic\n"

    markdown = (
        header
        + "\n"
        + bloco_1
        + "\n"
        + bloco_2
        + "\n"
        + bloco_3
        + "\n"
        + bloco_4
        + "\n"
        + bloco_5
        + "\n"
        + bloco_6
        + "\n"
        + bloco_7
        + "\n"
        + bloco_8
        + "\n"
        + bloco_9
        + bloco_10
    ).strip()

    return markdown, last_value, last_date, prev_value, prev_date, delta, pct_change, trend


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

        print("🟩 Construindo relatório estruturado...")
        (
            markdown,
            last_value,
            last_date,
            prev_value,
            prev_date,
            delta,
            pct_change,
            trend,
        ) = build_structured_report(obs)

        result = {
            "series_id": FRED_SERIES_ID,
            "last_value": last_value,
            "last_date": last_date,
            "prev_value": prev_value,
            "prev_date": prev_date,
            "delta": delta,
            "pct_change": pct_change,
            "trend": trend,
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
        print(f"❌ Erro ao gerar relatório de Coal: {e}")
        try:
            telegram_send_message(f"❌ Erro ao gerar relatório de Coal:\n`{e}`")
        except Exception as e2:
            print("Falha ao enviar mensagem de erro para o Telegram:", e2)
        raise


if __name__ == "__main__":
    main()
