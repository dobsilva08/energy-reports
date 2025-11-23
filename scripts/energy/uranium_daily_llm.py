#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Relatório Diário — Uranium (U3O8)
- 10 tópicos fixos
- Usa providers.llm_client (PIAPI + fallback)
- Trava diária (.sent) e contador
- Envio opcional ao Telegram
"""

# garante que o root do repo está no PYTHONPATH (igual gas_daily.py)
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
from scripts.gas.tools import title_counter, sent_guard, send_to_telegram
from scripts.energy.uranium_daily import fetch_uranium_from_fred  # reaproveita função já existente

BRT = timezone(timedelta(hours=-3))


def today_brt_str() -> str:
    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    now = datetime.now(BRT)
    return f"{now.day} de {meses[now.month-1]} de {now.year}"


def build_context_block(series_id: str = "PURANUSDM", start: str = "1990-01-01") -> str:
    """
    Busca a série de Urânio no FRED e monta um bloco de contexto factual
    para alimentar o LLM (preço atual, variação, período).
    """
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY não configurado no ambiente.")

    df = fetch_uranium_from_fred(api_key=api_key, series_id=series_id, observation_start=start)

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

    lines = [
        f"- Último preço spot (U3O8): {last_price:.4f} USD/lb em {last_date}.",
    ]

    if prev_date is not None:
        lines.append(
            f"- Leitura anterior: {prev_price:.4f} USD/lb em {prev_date}."
            f" Variação diária: {delta:+.4f} USD/lb ({delta_pct:+.2f}%)."
        )

    lines.extend(
        [
            f"- Período disponível na série FRED ({series_id}): {start_date} → {df['date'].max()}.",
            f"- Faixa histórica de preço: mínimo {min_price:.4f} USD/lb, máximo {max_price:.4f} USD/lb.",
            "- A série é mensal, refletindo o preço global de urânio U3O8 (global spot).",
            "- Mercado de urânio é relativamente ilíquido, com contratos bilaterais, oferta concentrada e pouca transparência.",
            "- Fundamentos-chave: produção em mineradoras (Cazaquistão, Canadá, Austrália), capacidade de enriquecimento e demanda de usinas nucleares.",
        ]
    )

    return "\n".join(lines)


def gerar_analise_uranio(contexto_textual: str, provider_hint: Optional[str] = None) -> Dict[str, Any]:
    system_msg = (
        "Você é um analista sênior de energia focado em urânio e ciclo do combustível nuclear. "
        "Escreva em PT-BR, claro, objetivo, com interpretação executiva e foco em preço, oferta, demanda e riscos."
    )

    user_msg = f"""
Gere um **Relatório Diário — Uranium (U3O8)** estruturado nos **10 tópicos abaixo**.
Seja específico e conciso. Numere exatamente de 1 a 10.

1) Preço spot de urânio (U3O8)
2) Curva de preço / termos contratuais (spot vs longo prazo)
3) Oferta (produção em mineradoras, capacidade de enriquecimento, estoques secundários)
4) Demanda (usinas nucleares em operação, construção e planejadas)
5) Estoques e contratos de utilities (segurança de suprimento, níveis de cobertura)
6) Custos de produção e incentivo a novos projetos (CAPEX, OPEX, break-even)
7) Geopolítica e riscos (sanções, restrições de exportação, instabilidade em países produtores)
8) Transição energética e narrativa institucional (papel da energia nuclear na descarbonização)
9) Interpretação Executiva (bullet points objetivos, até 5 linhas)
10) Conclusão (1 parágrafo: curto e médio prazo para preço do U3O8)

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
    parser = argparse.ArgumentParser(description="Relatório Diário — Uranium (U3O8)")
    parser.add_argument("--send-telegram", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--counter-path", default="data/counters.json")
    parser.add_argument("--sent-path", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--series-id", default=os.environ.get("URANIUM_FRED_SERIES_ID", "PURANUSDM"))
    parser.add_argument("--start", default="1990-01-01")
    args = parser.parse_args()

    sent_path = args.sent_path or "data/sentinels/uranium_daily.sent"

    # trava diária (evita envio duplicado)
    if not args.force and sent_guard(sent_path):
        print("Já foi enviado hoje (trava .sent). Use --force para ignorar.")
        return

    numero = title_counter(args.counter_path, key="diario_uranio")
    titulo = f"📊 Dados de Mercado — Uranium (U3O8) — {today_brt_str()} — Diário — Nº {numero}"

    contexto = build_context_block(series_id=args.series_id, start=args.start)

    t0 = time.time()
    llm_out = gerar_analise_uranio(contexto_textual=contexto, provider_hint=args.provider)
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
