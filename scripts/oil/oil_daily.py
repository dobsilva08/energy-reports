#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Relatório Diário — Petróleo (WTI & Brent)
- 10 tópicos fixos
- Usa LLMClient (PIAPI padrão + fallback Groq/OpenAI/DeepSeek)
- Trava diária (.sent) e contador
- Envio opcional ao Telegram
"""

import os, json, argparse, html, time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from providers.llm_client import LLMClient
from scripts.oil.fetch_prices import fetch_prices
from scripts.oil.tools import title_counter, sent_guard, send_to_telegram

BRT = timezone(timedelta(hours=-3))

def today_brt_str() -> str:
    meses = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    now = datetime.now(BRT)
    return f"{now.day} de {meses[now.month-1]} de {now.year}"

def build_context_block() -> str:
    prices = fetch_prices()
    partes = [
        f"- Preços: WTI ~ ${prices['wti']} ; Brent ~ ${prices['brent']} ; Spread (Brent-WTI) ~ ${prices['spread']}",
        "- Inventários (EIA/API/FRED): placeholder — integrar API para valores reais.",
        "- Produção: EUA / OPEP+ — estimativas e ritmo de recuperação.",
        "- Curva de Futuros: contango/backwardation (verificar curva de maturidades).",
        "- Refinarias / Crack Spreads: status atual e demanda por derivados.",
        "- Geopolítica: eventos recentes e riscos de oferta.",
    ]
    return "\n".join(partes)

def gerar_analise_oil(contexto_textual: str, provider_hint: Optional[str] = None) -> Dict[str, Any]:
    system_msg = (
        "Você é um analista financeiro sênior. Escreva em PT-BR, objetivo e claro, "
        "com dados e interpretação executiva. Evite jargão; mantenha coesão macro/indústria."
    )

    user_msg = f"""
Gere um **Relatório Diário — Petróleo (WTI & Brent)** estruturado nos **10 tópicos abaixo**.
Seja específico e conciso. Numere exatamente de 1 a 10.

1) Preços (WTI / Brent)
2) Spread Brent–WTI
3) Inventários (EIA/API/FRED)
4) Produção (EUA / OPEP+)
5) Curva de Futuros
6) Demanda Global (IEA/OECD)
7) Refinarias / Crack Spreads
8) Geopolítica
9) Interpretação Executiva (bullet points objetivos, até 5 linhas)
10) Conclusão (1 parágrafo, curto e médio prazo)

Baseie-se no contexto factual levantado:
{contexto_textual}
""".strip()

    llm = LLMClient(provider=provider_hint or None)
    texto = llm.generate(system_prompt=system_msg, user_prompt=user_msg, temperature=0.4, max_tokens=1800)
    return {"texto": texto, "provider": llm.active_provider}

def main():
    parser = argparse.ArgumentParser(description="Relatório Diário — Petróleo (WTI & Brent) — 10 tópicos")
    parser.add_argument("--send-telegram", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--counter-path", default="data/counters.json")
    parser.add_argument("--sent-path", default=None)
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()

    sent_path = args.sent_path or "data/sentinels/oil_daily.sent"

    if not args.force and sent_guard(sent_path):
        print("Já foi enviado hoje (trava .sent). Use --force para ignorar.")
        return

    numero = title_counter(args.counter_path, key="diario_oil")
    titulo = f"📊 Dados de Mercado — Petróleo (WTI & Brent) — {today_brt_str()} — Diário — Nº {numero}"

    contexto = build_context_block()
    t0 = time.time()
    llm_out = gerar_analise_oil(contexto_textual=contexto, provider_hint=args.provider)
    dt = time.time() - t0

    corpo = llm_out["texto"].strip()
    provider_usado = llm_out.get("provider", "?")
    texto_final = f"<b>{html.escape(titulo)}</b>\n\n{corpo}\n\n<i>Provedor LLM: {html.escape(str(provider_usado))} • {dt:.1f}s</i>"
    print(texto_final)

    if args.send_telegram:
        send_to_telegram(texto_final, preview=args.preview)

if __name__ == "__main__":
    main()
