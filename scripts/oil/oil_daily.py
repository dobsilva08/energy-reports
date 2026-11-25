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
Gere o **Relatório Diário — Petróleo (WTI + Brent)** com estrutura:\n\nPADRÃO VISUAL OBRIGATÓRIO ENERGY REPORTS:\n- Formate o texto para Telegram em estilo consistente com relatórios profissionais de commodities/on-chain/metais.\n- Use títulos de seção curtos com emoji e caixa alta, separadores simples (━━━━━━━━━━━━), bullets • e destaque somente números/termos-chave.\n- Organize: PRICE ACTION / DADOS; FUNDAMENTOS; OFERTA & DEMANDA ou estoques (quando pertinente); MACRO / GEOPOLÍTICA / RISCOS; INTERPRETAÇÃO EXECUTIVA; CENÁRIOS (curto e médio prazo); CONCLUSÃO. Adapte os subtítulos ao ativo e aos 10 tópicos solicitados sem inventar dados.\n- A seção INTERPRETAÇÃO EXECUTIVA deve ter 3 a 5 bullets objetivos e declarar viés (altista/baixista/neutro), momentum e principais catalisadores/riscos, apenas se sustentados pelo contexto.\n- Separe fatos fornecidos no contexto de inferências; sinalize dados indisponíveis e não invente cotações, pesquisas, notícias ou números.\n- Texto conciso, legível no Telegram, PT-BR, sem markdown de tabela, sem bloco de código e sem tags HTML (o wrapper já aplica HTML ao título).\n- Finalize com: “⚠️ Relatório informativo; não constitui recomendação de investimento.”\n

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

    final = f"<b>{html.escape(titulo)}</b>\n\n{texto}\n\n<i>LLM: {llm.active_provider} · {dt:.1f}s</i>"
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
