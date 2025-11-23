#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Relatório Diário — Jet Fuel (Kerosene de Aviação)
- 10 tópicos fixos
- Usa providers.llm_client (PIAPI + fallback)
- Trava diária (.sent) e contador
- Envio opcional ao Telegram
"""

import os
import sys

# garante que o root do repo está no PYTHONPATH (igual gas_daily.py)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import argparse
import html
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from providers.llm_client import LLMClient
from scripts.gas.tools import title_counter, sent_guard, send_to_telegram
from scripts.gas.jet_fuel_daily import fetch_jet_fuel_from_fred

BRT = timezone(timedelta(hours=-3))


def today_brt_str() -> str:
    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    now = datetime.now(BRT)
    return f"{now.day} de {meses[now.month-1]} de {now.year}"


def build_context_block(series_id: str = "DJFUELUSGULF", start: str = "2003-01-01") -> str:
    """
    Busca Jet Fuel no FRED e monta contexto factual
    (último preço, variação, faixa histórica, etc.) para o LLM.
    """
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY não configurado no ambiente.")

    df = fetch_jet_fuel_from_fred(
        api_key=api_key,
        series_id=series_id,
        observation_start=start,
    )

    df = df.sort_values("date").reset_index(drop=True)
    last = df.iloc[-1]
    last_date = last["date"]
    last_price = float(last["price"])

    if len(df) > 1:
        prev = df.iloc[-2]
        prev_date = prev["date"]
        prev_price = float(prev["price"])
        delta = last_price - prev_price
        delta_pct = (delta / prev_price) * 100 if prev_price != 0 else 0.0
    else:
        prev_date = None
        prev_price = None
        delta = 0.0
        delta_pct = 0.0

    min_price = float(df["price"].min())
    max_price = float(df["price"].max())
    start_date = df["date"].min()
    end_date = df["date"].max()

    lines = [
        f"- Último preço spot de Jet Fuel (proxy US Gulf): {last_price:.4f} USD/gal em {last_date}.",
    ]

    if prev_date is not None:
        lines.append(
            f"- Leitura anterior: {prev_price:.4f} USD/gal em {prev_date}. "
            f"Variação diária: {delta:+.4f} USD/gal ({delta_pct:+.2f}%)."
        )

    lines.extend(
        [
            f"- Período disponível na série FRED ({series_id}): {start_date} → {end_date}.",
            f"- Faixa histórica de preço: mínimo {min_price:.4f} USD/gal, máximo {max_price:.4f} USD/gal.",
            "- Jet Fuel (querosene de aviação) é um destilado médio, com demanda ligada a voos comerciais, carga aérea e tráfego doméstico/internacional.",
            "- Fundamentos-chave: capacidade de refino em destilados médios, utilização de refinarias, estoques de Jet nas principais regiões e fluxos internacionais.",
            "- Fatores de demanda: tráfego aéreo global (RPK, ASK), políticas de restrição de mobilidade, custos de passagens e fretes aéreos.",
            "- Spreads de Jet Fuel em relação a Brent/WTI (jet crack) são críticos para margens de companhias aéreas e refinarias.",
        ]
    )

    return "\n".join(lines)


def gerar_analise_jet_fuel(contexto_textual: str, provider_hint: Optional[str] = None) -> Dict[str, Any]:
    system_msg = (
        "Você é um analista sênior de energia focado em combustíveis de aviação (Jet Fuel). "
        "Escreva em PT-BR, claro, objetivo, com foco em preço, demanda de aviação, "
        "estoques, margens de refino e riscos."
    )

    user_msg = f"""
Gere um **Relatório Diário — Jet Fuel (Kerosene de Aviação)** estruturado nos **10 tópicos abaixo**.
Seja específico e conciso. Numere exatamente de 1 a 10.

1) Preço spot de Jet Fuel (região benchmark)
2) Curva de futuros e spreads (Jet vs Brent/WTI, jet crack spread)
3) Estoques de Jet Fuel e destilados médios (EIA / principais hubs)
4) Demanda de aviação (voos domésticos, internacionais, carga aérea; tráfego RPK/ASK quando disponível)
5) Capacidade e utilização de refinarias (foco em destilados médios e querosene de aviação)
6) Fluxos internacionais e arbitragem (rotas EUA–Europa–Ásia, hubs logísticos)
7) FX, custos de frete e tarifas aéreas (impactos em companhias aéreas e demanda)
8) Notas de Research / instituições (bancos, IEA, OACI, companhias aéreas)
9) Interpretação Executiva (bullet points objetivos, até 5 linhas)
10) Conclusão (1 parágrafo: curto e médio prazo para Jet Fuel)

Baseie-se no contexto factual levantado:
{contexto_textual}
""".strip()

    llm = LLMClient(provider=provider_hint or None)
    texto = llm.generate(
        system_prompt=system_msg,
        user_prompt=user_msg,
        temperature=0.35,
        max_tokens=1600,
    )
    return {"texto": texto, "provider": llm.active_provider}


def main():
    parser = argparse.ArgumentParser(description="Relatório Diário — Jet Fuel (Kerosene de Aviação)")
    parser.add_argument("--send-telegram", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--counter-path", default="data/counters.json")
    parser.add_argument("--sent-path", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument(
        "--series-id",
        default=os.environ.get("JET_FUEL_FRED_SERIES_ID", "DJFUELUSGULF"),
    )
    parser.add_argument("--start", default="2003-01-01")
    args = parser.parse_args()

    sent_path = args.sent_path or "data/sentinels/jet_fuel_daily.sent"

    # trava diária (evita envio duplicado)
    if not args.force and sent_guard(sent_path):
        print("Já foi enviado hoje (trava .sent). Use --force para ignorar.")
        return

    numero = title_counter(args.counter_path, key="diario_jet_fuel")
    titulo = f"✈️ Jet Fuel — Relatório Diário — {today_brt_str()} — Nº {numero}"

    contexto = build_context_block(series_id=args.series_id, start=args.start)

    t0 = time.time()
    llm_out = gerar_analise_jet_fuel(contexto_textual=contexto, provider_hint=args.provider)
    dt = time.time() - t0

    corpo = llm_out["texto"].strip()
    provider_usado = llm_out.get("provider", "?")

    texto_final = (
        f"<b>{html.escape(titulo)}</b>\n\n"
        f"{corpo}\n\n"
        f"<i>Provedor LLM: {html.escape(str(provider_usado))} • {dt:.1f}s</i>"
    )

    print(texto_final)

    if args.send_telegram:
        send_to_telegram(texto_final, preview=args.preview)


if __name__ == "__main__":
    main()
