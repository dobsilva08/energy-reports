#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Corrige caminho raiz
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import time
import html
from datetime import datetime, timezone, timedelta

from providers.llm_client import LLMClient
from scripts.oil.fetch_prices import get_wti_price, get_brent_price
from scripts.oil.tools import (
    sentinel_trigger,
    mark_sent,
    increment_counter,
    send_telegram,
    today_brt,
)


BRT = timezone(timedelta(hours=-3))


def run_daily(preview=False):

    # -------------------
    # Sentinel
    # -------------------
    sent_path = "data/sentinels/oil_daily.sent"

    if sentinel_trigger(sent_path):
        print("Já enviado hoje. Abortar.")
        return

    # -------------------
    # Dados
    # -------------------
    wti = get_wti_price()
    brent = get_brent_price()

    contexto = f"- WTI: USD {wti:.2f}" if wti is not None else "- WTI: indisponível (API não retornou dado válido)"
    contexto += f"\n- Brent: USD {brent:.2f}" if brent is not None else "\n- Brent: indisponível (API não retornou dado válido)"


    # -------------------
    # LLM
    # -------------------
    system = (
        "Você é um analista sênior de energia. Responda em PT-BR, "
        "objetivo, direto e com análise macro."
    )

    user = f"""
Gere o **Relatório Diário — Petróleo (WTI + Brent)** com estrutura:\n\nPADRÃO EDITORIAL E VISUAL ENERGY REPORTS (OBRIGATÓRIO — NÃO OMITIR):
Produza um relatório com visual de boletim profissional de mercado, não um texto corrido. Use HTML compatível com Telegram (somente <b>, <i>, <code>), sem Markdown.
Formato fixo:
🟠 <b>ENERGY REPORTS | [ATIVO]</b>
📅 Data e período

━━━━━━━━━━━━━━━━━━
⚡ <b>PAINEL DE MERCADO</b>
• preço/benchmark e unidade
• variação e direção, somente se houver dado
• 2–4 indicadores-chave (N/D quando indisponíveis)

━━━━━━━━━━━━━━━━━━
🧭 <b>LEITURA EXECUTIVA</b>
• 3 bullets curtos: viés, momentum, catalisador/riscos, sem extrapolar

━━━━━━━━━━━━━━━━━━
📊 <b>FUNDAMENTOS</b>
• Oferta, demanda, estoques, produção, curva/spreads, conforme aplicável

━━━━━━━━━━━━━━━━━━
🌐 <b>MACRO & GEOPOLÍTICA</b>
• fatores macro, clima, logística, política ou risco relevantes

━━━━━━━━━━━━━━━━━━
🔎 <b>O QUE MONITORAR</b>
• 3 próximos indicadores/eventos, sem inventar datas

━━━━━━━━━━━━━━━━━━
🎯 <b>CENÁRIOS</b>
🟢 Altista: condição que sustentaria
🟡 Base: cenário neutro / continuidade
🔴 Baixista: condição que pressionaria
Não invente níveis de preço nem probabilidades.

━━━━━━━━━━━━━━━━━━
📝 <b>CONCLUSÃO</b>
Um parágrafo curto com horizonte curto/médio e grau de confiança baseado nos dados.

━━━━━━━━━━━━━━━━━━
Use bullets •, subtítulos com emoji e separadores. Compacto e bem hierarquizado. Dados ausentes explicitamente como N/D. Não use texto genérico para preencher lacunas.

1) Preços WTI e Brent
2) Futuros, curva e spreads
3) Estoques (EIA/API)
4) Produção global (OPEC+, EUA, shale)
5) Demanda global
6) Geopolítica e riscos
7) FX (DXY) e Treasuries
8) Notas de pesquisa e instituições
9) Interpretação executiva (bullet points)
10) Conclusão (curto e médio prazo)

Use os dados:
{contexto}
"""

    llm = LLMClient()
    t0 = time.time()
    texto = llm.generate(system, user, temperature=0.4, max_tokens=1800)
    dt = time.time() - t0

    num = increment_counter("data/counters.json", "oil_daily")
    titulo = f"🛢️ Petróleo — Relatório Diário (Brent & WTI) — {today_brt()} — Diário — Nº {num}"

    final = f"<b>{html.escape(titulo)}</b>\n\n{texto}"
    print(final)

    send_telegram(final, preview=preview)
    if not preview:
        mark_sent(sent_path)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--preview", action="store_true")
    p.add_argument("--send-telegram", action="store_true")

    args = p.parse_args()

    run_daily(preview=args.preview)
