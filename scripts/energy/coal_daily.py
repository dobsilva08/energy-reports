import os
import json
import argparse
import requests
import time
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# LLM Client com fallback (PIAPI, Groq, OpenAI, DeepSeek)
# ------------------------------------------------------------------
try:
    # pressupondo que o arquivo fornecido por você está em llm_client.py na raiz
    from llm_client import LLMClient
except ImportError:
    LLMClient = None

# detecta se existe alguma chave de LLM configurada
HAS_LLM_KEYS = any(
    os.getenv(k)
    for k in ["PIAPI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"]
)

# ------------------------------------------------------------------
# Variáveis de ambiente base
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
FRED_SERIES_ID = "WPU051"  # Producer Price Index: Coal (1982=100)

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
# Métricas básicas a partir da série
# ------------------------------------------------------------------
def compute_metrics(obs):
    last = obs[-1]
    last_value = float(last["value"])
    last_date = last["date"]

    if len(obs) >= 2:
        prev = obs[-2]
        prev_value = float(prev["value"])
        prev_date = prev["date"]
        delta = last_value - float(prev["value"])
        pct = (delta / prev_value) * 100 if prev_value != 0 else 0.0
    else:
        prev_value = None
        prev_date = None
        delta = 0.0
        pct = 0.0

    if pct > 0.5:
        trend = "alta"
    elif pct < -0.5:
        trend = "queda"
    else:
        trend = "estabilidade"

    return {
        "last_value": last_value,
        "last_date": last_date,
        "prev_value": prev_value,
        "prev_date": prev_date,
        "delta": delta,
        "pct_change": pct,
        "trend": trend,
    }


# ------------------------------------------------------------------
# TEMPLATE (sem IA) – modo fallback
# ------------------------------------------------------------------
def build_structured_report_template(metrics):
    today_str = datetime.utcnow().date().isoformat()

    last_value = metrics["last_value"]
    last_date = metrics["last_date"]
    prev_value = metrics["prev_value"]
    prev_date = metrics["prev_date"]
    delta = metrics["delta"]
    pct_change = metrics["pct_change"]
    trend = metrics["trend"]

    if trend == "alta":
        exec_trend = (
            "Índice de carvão em alta, sugerindo pressão de custos na cadeia energética."
        )
        curto_prazo = (
            "Pressão altista no curto prazo, com repasse de custos para cadeias intensivas em carvão."
        )
    elif trend == "queda":
        exec_trend = (
            "Índice de carvão em queda, abrindo espaço para redução de custos industriais."
        )
        curto_prazo = (
            "Pressão baixista no curto prazo, com algum alívio para setores dependentes de carvão."
        )
    else:
        exec_trend = (
            "Índice de carvão relativamente estável, sem choques de preço relevantes no dia."
        )
        curto_prazo = (
            "Movimento lateralizado no curto prazo, com mercado equilibrando oferta, demanda e transição energética."
        )

    medio_prazo = (
        "No médio prazo, políticas climáticas, descarbonização e competitividade de gás e renováveis "
        "tendem a limitar a alta estrutural do carvão, ainda que choques regionais possam gerar picos temporários."
    )

    texto = f"📊 <b>Coal — {today_str} — Diário</b>\n\n"
    texto += "<b>Relatório Diário — Índice de Carvão (PPI – WPU051)</b>\n\n"

    # 1)
    texto += "1) <b>Índice PPI – Coal</b>\n"
    texto += f"   • Valor mais recente: <b>{last_value:,.2f}</b>\n"
    texto += f"   • Data: {last_date}\n"
    if prev_value is not None:
        sinal = "+" if delta >= 0 else "-"
        texto += f"   • Leitura anterior: {prev_value:,.2f} ({prev_date})\n"
        texto += (
            f"   • Variação diária: {sinal}{abs(delta):,.2f} pontos "
            f"({sinal}{abs(pct_change):.2f}%)\n"
        )

    # 2)
    texto += "\n2) <b>Estrutura e tendência</b>\n"
    texto += f"   • Cenário atual: <b>{trend}</b>.\n"
    texto += (
        "   • O índice reflete contratos de fornecimento, custos de extração e logística.\n"
    )

    # 3)
    texto += "\n3) <b>Oferta</b>\n"
    texto += (
        "   • Capacidade de mineração, custos trabalhistas e restrições regulatórias "
        "influenciam a oferta de carvão.\n"
    )

    # 4)
    texto += "\n4) <b>Demanda</b>\n"
    texto += (
        "   • Determinada por geração termoelétrica, aço, cimento e demais indústrias intensivas em energia.\n"
    )

    # 5)
    texto += "\n5) <b>Transição energética</b>\n"
    texto += (
        "   • A migração gradual para gás e renováveis reduz estruturalmente a participação do carvão.\n"
    )

    # 6)
    texto += "\n6) <b>FX (DXY) e condições financeiras</b>\n"
    texto += (
        "   • Um dólar mais forte tende a pressionar commodities energéticas para países importadores.\n"
    )

    # 7)
    texto += "\n7) <b>Instituições e pesquisas</b>\n"
    texto += (
        "   • Agências de energia projetam queda gradual no uso de carvão, embora partindo de base ainda elevada.\n"
    )

    # 8)
    texto += "\n8) <b>Interpretação executiva</b>\n"
    texto += f"   • {exec_trend}\n"
    texto += (
        "   • Setores eletrointensivos permanecem sensíveis a choques de preço no índice de carvão.\n"
    )

    # 9)
    texto += "\n9) <b>Conclusão (curto e médio prazo)</b>\n"
    texto += f"   • <b>Curto prazo:</b> {curto_prazo}\n"
    texto += f"   • <b>Médio prazo:</b> {medio_prazo}\n"

    # 10) rodapé
    texto += "\n<i>Modo: template (sem LLM)</i>"

    return {
        "html": texto,
        **metrics,
        "provider": "template",
        "llm_used": False,
        "llm_time": None,
    }


# ------------------------------------------------------------------
# Versão com IA REAL — usando LLMClient (PIAPI / Groq / OpenAI / DeepSeek)
# ------------------------------------------------------------------
def build_structured_report_llm(metrics):
    """
    Gera o relatório usando LLMClient, em português, formato HTML compatível com Telegram.
    Usa fallback automático entre PIAPI, Groq, OpenAI e DeepSeek.
    """
    if LLMClient is None:
        raise RuntimeError("LLMClient não disponível (módulo llm_client não encontrado).")

    client = LLMClient()

    today_str = datetime.utcnow().date().isoformat()

    # compacta algumas observações para contexto (últimos 10 pontos)
    # Aqui usamos só as métricas calculadas (valor atual, anterior, variação, tendência)
    last_value = metrics["last_value"]
    last_date = metrics["last_date"]
    prev_value = metrics["prev_value"]
    prev_date = metrics["prev_date"]
    delta = metrics["delta"]
    pct_change = metrics["pct_change"]
    trend = metrics["trend"]

    system_prompt = (
        "Você é um analista de energia especializado em carvão e mercado de energia global.\n"
        "Escreva em português do Brasil, de forma clara, técnica e executiva.\n"
        "Saída obrigatória em HTML simples, compatível com Telegram, usando apenas <b>, <i> e quebras de linha.\n"
        "Não use listas HTML (<ul>, <ol>), apenas texto com '1)', '2)' etc.\n"
        "Não inclua tags <html>, <body> ou cabeçalho de documento, apenas o conteúdo."
    )

    # monta prompt com os dados quantitativos
    resumo_dados = f"""
Dados da série PPI – Coal (WPU051):

- Valor mais recente: {last_value:.2f} (data {last_date})
- Valor anterior: {prev_value if prev_value is not None else 'N/A'} (data {prev_date if prev_date else 'N/A'})
- Variação absoluta: {delta:.2f}
- Variação percentual: {pct_change:.2f}%
- Tendência simples: {trend}
- Data de referência do relatório: {today_str}
"""

    user_prompt = (
        resumo_dados
        + """

Com base nesses dados, escreva um RELATÓRIO DIÁRIO de carvão com exatamente esta estrutura:

1) Cabeçalho:
   - Primeira linha: 📊 <b>Coal — AAAA-MM-DD — Diário</b>
   - Segunda linha: <b>Relatório Diário — Índice de Carvão (PPI – WPU051)</b>

2) Seções numeradas de 1 a 9, em texto corrido, seguindo o padrão:
   1) Índice PPI – Coal (nível atual, variação, leitura anterior)
   2) Estrutura de preços e tendência
   3) Fatores de oferta
   4) Fatores de demanda
   5) Transição energética e substituição
   6) FX (DXY) e condições financeiras
   7) Notas de pesquisa e instituições
   8) Interpretação executiva (bullet points em texto, começando com '•')
   9) Conclusão (curto e médio prazo)

3) No final, inclua UMA linha de rodapé:
   <i>Provedor LLM: {provider} • X.Xs</i>

Onde {provider} deve ser o nome do provider ativo (por exemplo piapi, groq, openai, deepseek)
e X.X é apenas um placeholder; o tempo real será ajustado pelo código.

Regras:
- Use sempre quebras de linha '\\n' entre parágrafos.
- Use <b> para destacar termos importantes.
- Não coloque markdown com **asteriscos**; use apenas HTML.
- Não invente dados de preço específicos além dos que foram fornecidos, mas pode interpretar tendências.
"""
    )

    t0 = time.time()
    raw_html = client.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.35,
        max_tokens=1800,
    )
    elapsed = time.time() - t0
    provider = client.active_provider or "desconhecido"

    # garante texto "limpo"
    html = raw_html.strip()

    # adiciona/ajusta rodapé
    rodape = f"\n\n<i>Provedor LLM: {provider} • {elapsed:.1f}s</i>"
    if "Provedor LLM:" in html:
        # se o modelo já colocou algo, apenas anexamos a linha padrão no final
        html += rodape
    else:
        html += rodape

    return {
        "html": html,
        **metrics,
        "provider": provider,
        "llm_used": True,
        "llm_time": elapsed,
    }


# ------------------------------------------------------------------
# Escolha entre IA (se disponível) e template
# ------------------------------------------------------------------
def build_structured_report(obs):
    metrics = compute_metrics(obs)

    if HAS_LLM_KEYS and LLMClient is not None:
        try:
            print("LLM disponível – gerando relatório com IA (LLMClient)...")
            return build_structured_report_llm(metrics)
        except Exception as e:
            print("Erro ao usar LLM, caindo para template:", e)
            return build_structured_report_template(metrics)
    else:
        print("Nenhuma chave de LLM encontrada ou LLMClient indisponível – usando template.")
        return build_structured_report_template(metrics)


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

        print("🟩 Construindo relatório estruturado (IA opcional)...")
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

        print("📨 Enviando relatório para o Telegram (mensagem única)...")
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
