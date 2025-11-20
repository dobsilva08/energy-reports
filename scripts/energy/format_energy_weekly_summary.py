#!/usr/bin/env python3
"""
Gera um resumo consolidado ENERGY — Weekly Macro Summary
a partir dos 3 CSVs já gerados:

 - /tmp/petroleum_crude.csv
 - /tmp/petroleum_products.csv
 - /tmp/gas_storage.csv

Saída:
 - /tmp/telegram_energy_summary.txt  (mensagem em Markdown para Telegram)
"""

import argparse
from datetime import datetime
import pandas as pd


def latest_stats(df: pd.DataFrame, value_col: str = "value"):
    """Retorna stats da última leitura + delta WoW."""
    if df is None or len(df) == 0:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None

    date_latest = pd.to_datetime(latest["date"]).date()
    v_latest = float(latest[value_col]) if pd.notna(latest[value_col]) else None

    if prev is not None and pd.notna(prev[value_col]) and v_latest is not None:
        prev_v = float(prev[value_col])
        delta = v_latest - prev_v
        pct = (delta / prev_v) * 100 if prev_v != 0 else 0.0
    else:
        delta = 0.0
        pct = 0.0

    return {
        "date": date_latest,
        "value": v_latest,
        "delta": delta,
        "pct": pct,
    }


def interpret_petroleum(delta_pct: float) -> str:
    if delta_pct <= -1.5:
        return "Bullish — forte queda semanal nos estoques"
    if delta_pct <= -0.5:
        return "Levemente bullish — estoques recuando"
    if delta_pct >= 1.5:
        return "Bearish — forte aumento semanal nos estoques"
    if delta_pct >= 0.5:
        return "Levemente bearish — estoques subindo"
    return "Neutro — movimento semanal pequeno"


def interpret_gas(delta_bcf: float) -> str:
    if delta_bcf <= -50:
        return "Saída excepcional — risco de tightness elevado"
    if delta_bcf <= -10:
        return "Saída forte — suporte a preços de gás"
    if delta_bcf < 0:
        return "Saída moderada — ambiente ligeiramente bullish"
    if delta_bcf >= 50:
        return "Injeção excepcional — cenário de folga"
    if delta_bcf >= 10:
        return "Injeção forte — pressão de baixa no gás"
    return "Movimento moderado — sem grande desvio"


def crude_4w_trend(df: pd.DataFrame, value_col: str = "value"):
    """Mede a tendência de 4 semanas para crude (apenas para o comentário macro)."""
    if df is None or len(df) < 5:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    last = float(df[value_col].iloc[-1])
    prev_4 = float(df[value_col].iloc[-5])
    delta = last - prev_4
    pct = (delta / prev_4) * 100 if prev_4 != 0 else 0.0
    return {"delta": delta, "pct": pct}


def macro_view(crude_stats, products_stats, gas_stats, crude_trend_4w):
    """Gera uma frase macro consolidada."""
    parts = []

    # visão petróleo
    if crude_stats:
        if crude_stats["pct"] <= -1.0:
            parts.append("estoques de petróleo bruto em queda, sugerindo leve tightening na oferta")
        elif crude_stats["pct"] >= 1.0:
            parts.append("estoques de petróleo bruto em alta, indicando algum alívio de oferta")
        else:
            parts.append("estoques de petróleo bruto praticamente estáveis na semana")

    # visão produtos
    if products_stats:
        if products_stats["pct"] <= -0.5:
            parts.append("estoques totais (crude + produtos) também recuando")
        elif products_stats["pct"] >= 0.5:
            parts.append("estoques totais (crude + produtos) avançando")
        # se perto de zero, não adiciono nada pra não poluir

    # visão gás
    if gas_stats:
        if gas_stats["delta"] <= -10:
            parts.append("no gás natural, a saída semanal do storage reforça um viés mais apertado")
        elif gas_stats["delta"] >= 10:
            parts.append("no gás natural, a injeção de volumes aponta para ambiente mais folgado")

    # tendência 4 semanas
    if crude_trend_4w:
        if crude_trend_4w["pct"] <= -3:
            parts.append("na janela de 4 semanas, o crude segue em tendência de queda consistente")
        elif crude_trend_4w["pct"] >= 3:
            parts.append("na janela de 4 semanas, o crude mostra acúmulo relevante de estoques")

    if not parts:
        return "Quadro semanal relativamente neutro, sem grandes desequilíbrios aparentes."

    # junta tudo em uma frase fluida
    texto = "; ".join(parts)
    # capitaliza
    texto = texto[0].upper() + texto[1:] + "."
    return texto


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--crude", required=True)
    p.add_argument("--products", required=True)
    p.add_argument("--gas", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    df_crude = pd.read_csv(args.crude)
    df_products = pd.read_csv(args.products)
    df_gas = pd.read_csv(args.gas)

    for df in (df_crude, df_products, df_gas):
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

    crude_stats = latest_stats(df_crude, "value")
    products_stats = latest_stats(df_products, "value")
    gas_stats = latest_stats(df_gas, "storage_bcf")

    crude_trend4 = crude_4w_trend(df_crude, "value")

    # linhas principais
    msg_lines = []

    msg_lines.append("📊 *ENERGY — Weekly Macro Summary*\n")

    # data de referência (usa crude)
    ref_date = crude_stats["date"] if crude_stats else None
    if ref_date:
        msg_lines.append(f"🗓 *Referência semanal:* {ref_date}\n")

    if crude_stats:
        msg_lines.append(
            "🛢️ *Crude (Ex-SPR)*: "
            f"{crude_stats['value']:,.0f} bbl | "
            f"{crude_stats['delta']:+,.0f} bbl WoW "
            f"({crude_stats['pct']:+.2f}%) — "
            f"{interpret_petroleum(crude_stats['pct'])}"
        )

    if products_stats:
        msg_lines.append(
            "🛢️ *Crude + Products (Total US)*: "
            f"{products_stats['value']:,.0f} bbl | "
            f"{products_stats['delta']:+,.0f} bbl WoW "
            f"({products_stats['pct']:+.2f}%) — "
            f"{interpret_petroleum(products_stats['pct'])}"
        )

    if gas_stats:
        msg_lines.append(
            "⛽ *Gas Storage (Lower 48)*: "
            f"{gas_stats['value']:,.1f} Bcf | "
            f"{gas_stats['delta']:+.1f} Bcf WoW "
            f"({gas_stats['pct']:+.2f}%) — "
            f"{interpret_gas(gas_stats['delta'])}"
        )

    msg_lines.append("")  # linha em branco

    # visão macro consolidada
    macro = macro_view(crude_stats, products_stats, gas_stats, crude_trend4)
    msg_lines.append(f"🧭 *Leitura macro da semana:*\n{macro}\n")

    # comentário sobre tendência 4 semanas
    if crude_trend4:
        msg_lines.append(
            "📉 *Tendência 4 semanas (Crude)*: "
            f"{crude_trend4['delta']:+,.0f} bbl desde 4 semanas atrás "
            f"({crude_trend4['pct']:+.2f}%)."
        )

    msg_lines.append("\n🔗 Dados detalhados: relatórios individuais de Petroleum & Gas Storage.")

    final_msg = "\n".join(msg_lines)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(final_msg)

    print("WROTE", args.out)


if __name__ == "__main__":
    main()
