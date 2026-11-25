#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Relatório Diário — Natural Gas (Henry Hub)
- 10 tópicos fixos
- Usa providers.llm_client (PIAPI + fallback)
- Trava diária (.sent) e contador
- Envio opcional ao Telegram
"""

# ensure repo root in path so `providers` resolves on runners
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import argparse
import html
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from providers.llm_client import LLMClient
from scripts.gas.fetch_prices import fetch_prices
from scripts.gas.tools import title_counter, sent_guard, send_to_telegram

BRT = timezone(timedelta(hours=-3))

def today_brt_str() -> str:
    meses = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    now = datetime.now(BRT)
    return f"{now.day} de {meses[now.month-1]} de {now.year}"

def build_context_block() -> str:
    prices = fetch_prices()
    parts = [
        f"- Henry Hub (spot): {prices.get('henry_hub_spot')} {prices.get('unit', 'USD/MMBtu')}",
        f"- Front-month future: {prices.get('front_month')} {prices.get('unit', 'USD/MMBtu')}",
        "- Estoques (EIA): ver weekly report (se EIA_API_KEY estiver disponível integrará automaticamente).",
        "- Produção (EUA/Marcellus/Powder River/Permian): tendência e rig counts (placeholder).",
        "- Demanda (geração elétrica, residen/al, industrial): sazonalidade importante (inverno/verão).",
        "- Geopolítica / climatologia (temperaturas, frio extremo, interrupções de fornecimento).",
        "- Curva de futuros: contango vs backwardation — risco de roll.",
    ]
    return "\n".join(parts)

def gerar_analise_gas(contexto_textual: str, provider_hint: Optional[str] = None) -> Dict[str, Any]:
    system_msg = (
        "Você é um analista sênior de energia (gás natural). Escreva em PT-BR, "
        "claro, objetivo, com interpretação executiva e dados resumidos."
    )
    user_msg = f"""
Gere um **Relatório Diário — Natural Gas (Henry Hub)** estruturado nos **10 tópicos abaixo**.\n\nPADRÃO VISUAL OBRIGATÓRIO ENERGY REPORTS:\n- Formate o texto para Telegram em estilo consistente com relatórios profissionais de commodities/on-chain/metais.\n- Use títulos de seção curtos com emoji e caixa alta, separadores simples (━━━━━━━━━━━━), bullets • e destaque somente números/termos-chave.\n- Organize: PRICE ACTION / DADOS; FUNDAMENTOS; OFERTA & DEMANDA ou estoques (quando pertinente); MACRO / GEOPOLÍTICA / RISCOS; INTERPRETAÇÃO EXECUTIVA; CENÁRIOS (curto e médio prazo); CONCLUSÃO. Adapte os subtítulos ao ativo e aos 10 tópicos solicitados sem inventar dados.\n- A seção INTERPRETAÇÃO EXECUTIVA deve ter 3 a 5 bullets objetivos e declarar viés (altista/baixista/neutro), momentum e principais catalisadores/riscos, apenas se sustentados pelo contexto.\n- Separe fatos fornecidos no contexto de inferências; sinalize dados indisponíveis e não invente cotações, pesquisas, notícias ou números.\n- Texto conciso, legível no Telegram, PT-BR, sem markdown de tabela, sem bloco de código e sem tags HTML (o wrapper já aplica HTML ao título).\n- Finalize com: “⚠️ Relatório informativo; não constitui recomendação de investimento.”\n
Seja específico e conciso. Numere exatamente de 1 a 10.

1) Preço spot (Henry Hub)
2) Front-month / curva de futuros
3) Estoques (EIA)
4) Produção (EUA / principais bacias)
5) Demanda (Geração elétrica, residencial, industrial)
6) Interligações / LNG exports (impacto em spreads)
7) Clima / Sazonalidade (temperatura, grip)
8) Notas de Research / institucionais
9) Interpretação Executiva (bullet points objetivos, até 5 linhas)
10) Conclusão (1 parágrafo: curto e médio prazo)

Baseie-se no contexto factual levantado:
{contexto_textual}
""".strip()

    llm = LLMClient(provider=provider_hint or None)
    texto = llm.generate(system_prompt=system_msg, user_prompt=user_msg, temperature=0.35, max_tokens=1600)
    return {"texto": texto, "provider": llm.active_provider}

def main():
    parser = argparse.ArgumentParser(description="Relatório Diário — Natural Gas (Henry Hub)")
    parser.add_argument("--send-telegram", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--counter-path", default="data/counters.json")
    parser.add_argument("--sent-path", default=None)
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()

    sent_path = args.sent_path or "data/sentinels/gas_daily.sent"

    if not args.force and sent_guard(sent_path):
        print("Já foi enviado hoje (trava .sent). Use --force para ignorar.")
        return

    numero = title_counter(args.counter_path, key="diario_gas")
    titulo = f"🔥 Gás Natural — Relatório Diário (Henry Hub) — {today_brt_str()} — Nº {numero}"


    contexto = build_context_block()
    t0 = time.time()
    llm_out = gerar_analise_gas(contexto_textual=contexto, provider_hint=args.provider)
    dt = time.time() - t0

    corpo = llm_out["texto"].strip()
    provider_usado = llm_out.get("provider", "?")
    texto_final = f"<b>{html.escape(titulo)}</b>\n\n{corpo}\n\n<i>Provedor LLM: {html.escape(str(provider_usado))} • {dt:.1f}s</i>"
    print(texto_final)

    if args.send_telegram:
        send_to_telegram(texto_final, preview=args.preview)

if __name__ == "__main__":
    main()
