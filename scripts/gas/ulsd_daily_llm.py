#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Relatório Diário — ULSD (Ultra-Low Sulfur Diesel / Heating Oil)
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
from scripts.gas.ulsd_daily import fetch_ulsd_from_fred

BRT = timezone(timedelta(hours=-3))


def today_brt_str() -> str:
    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
    ]
    now = datetime.now(BRT)
    return f"{now.day} de {meses[now.month-1]} de {now.year}"


def build_context_block(series_id: str = "DDFUELUSGULF", start: str = "2003-01-01") -> str:
    """
    Busca ULSD no FRED e monta bloco de contexto factual
    (último preço, variação, faixa histórica, etc.) para o LLM.
    """
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY não configurado no ambiente.")

    df = fetch_ulsd_from_fred(
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
        f"- Último preço spot ULSD (proxy Heating Oil): {last_price:.4f} USD/gal em {last_date}.",
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
            "- ULSD/Heating Oil é um destilado médio, próximo de diesel, usado como proxy para margens de refino em transporte rodoviário e aquecimento.",
            "- Fundamentos-chave: capacidade de refino em destilados médios, demanda sazonal (aquecimento no inverno, transporte), estoques da EIA e spreads em relação ao WTI/Brent.",
            "- Curva de futuros de HO/ULSD e crack spreads influenciam decisões de hedge de refinarias e distribuidores.",
        ]
    )

    return "\n".join(lines)


def gerar_analise_ulsd(contexto_textual: str, provider_hint: Optional[str] = None) -> Dict[str, Any]:
    system_msg = (
        "Você é um analista sênior de produtos refinados (ULSD / Heating Oil). "
        "Escreva em PT-BR, claro, objetivo, com foco em preço, margens de refino, "
        "estoques, demanda e riscos. Respeite a estrutura pedida."
    )

    user_msg = f"""
Gere um **Relatório Diário — ULSD / Heating Oil** estruturado nos **10 tópicos abaixo**.\n\nPADRÃO VISUAL OBRIGATÓRIO ENERGY REPORTS:\n- Formate o texto para Telegram em estilo consistente com relatórios profissionais de commodities/on-chain/metais.\n- Use títulos de seção curtos com emoji e caixa alta, separadores simples (━━━━━━━━━━━━), bullets • e destaque somente números/termos-chave.\n- Organize: PRICE ACTION / DADOS; FUNDAMENTOS; OFERTA & DEMANDA ou estoques (quando pertinente); MACRO / GEOPOLÍTICA / RISCOS; INTERPRETAÇÃO EXECUTIVA; CENÁRIOS (curto e médio prazo); CONCLUSÃO. Adapte os subtítulos ao ativo e aos 10 tópicos solicitados sem inventar dados.\n- A seção INTERPRETAÇÃO EXECUTIVA deve ter 3 a 5 bullets objetivos e declarar viés (altista/baixista/neutro), momentum e principais catalisadores/riscos, apenas se sustentados pelo contexto.\n- Separe fatos fornecidos no contexto de inferências; sinalize dados indisponíveis e não invente cotações, pesquisas, notícias ou números.\n- Texto conciso, legível no Telegram, PT-BR, sem markdown de tabela, sem bloco de código e sem tags HTML (o wrapper já aplica HTML ao título).\n- Finalize com: “⚠️ Relatório informativo; não constitui recomendação de investimento.”\n
Seja específico e conciso. Numere exatamente de 1 a 10.

1) Preço spot ULSD / Heating Oil
2) Curva de futuros e spreads (HO vs WTI/Brent, crack spreads)
3) Estoques de destilados médios (EIA) e utilização de refinarias
4) Demanda (transporte, aquecimento, uso industrial e marítimo)
5) Produção/refino (paradas, gargalos regionais, manutenção)
6) Fluxos internacionais e arbitragem (Europa, EUA, América Latina)
7) FX, fretes e custos logísticos (impacto em spreads regionais)
8) Notas de Research / instituições (visão de bancos, agências, casas de análise)
9) Interpretação Executiva (bullet points objetivos, até 5 linhas)
10) Conclusão (1 parágrafo: curto e médio prazo para ULSD / destilados)

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
    parser = argparse.ArgumentParser(description="Relatório Diário — ULSD / Heating Oil")
    parser.add_argument("--send-telegram", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--counter-path", default="data/counters.json")
    parser.add_argument("--sent-path", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument(
        "--series-id",
        default=os.environ.get("ULSD_FRED_SERIES_ID", "DDFUELUSGULF"),
    )
    parser.add_argument("--start", default="2003-01-01")
    args = parser.parse_args()

    sent_path = args.sent_path or "data/sentinels/ulsd_daily.sent"

    # trava diária (evita envio duplicado)
    if not args.force and sent_guard(sent_path):
        print("Já foi enviado hoje (trava .sent). Use --force para ignorar.")
        return

    numero = title_counter(args.counter_path, key="diario_ulsd")
    titulo = f"🚚 Diesel ULSD — Relatório Diário — {today_brt_str()} — Nº {numero}"

    contexto = build_context_block(series_id=args.series_id, start=args.start)

    t0 = time.time()
    llm_out = gerar_analise_ulsd(contexto_textual=contexto, provider_hint=args.provider)
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
