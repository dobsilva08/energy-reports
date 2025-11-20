#!/usr/bin/env python3
"""
Formata 3 mensagens Telegram (uma por ativo) a partir dos CSVs:
 - crude
 - products
 - gas
"""

import argparse
import pandas as pd
from datetime import datetime


# Mapeamento manual dos nomes oficiais da EIA (fallback)
SERIES_NAMES = {
    "PET.WCESTUS1.W": "Weekly U.S. Ending Stocks of Crude Oil (Excluding SPR)",
    "PET.WTTSTUS1.W": "Weekly U.S. Total Stocks of Crude Oil and Petroleum Products",
    "NG.NW2_EPG0_SWO_R48_BCF.W": "Working Gas in Underground Storage — Lower 48 (Bcf)",
}


def resolve_series_name(series_id, existing_label):
    """
    Usa o nome da EIA se vier pelo CSV; senão, aplica fallback manual.
    """
    if isinstance(existing_label, str) and existing_label.strip() not in ("", "nan", "None"):
        return existing_label

    # fallback inteligente
    return SERIES_NAMES.get(series_id, f"Série {series_id}")


def latest_stats(df: pd.DataFrame, value_col: str = "value"):
    if df is None or len(df) == 0:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None

    # resolve nome com fallback
    s_id = latest.get("series_id")
    s_label = resolve_series_name(s_id, latest.get("label"))

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
        "label": s_label,
        "series_id": s_id,
    }


def interpret_petroleum(delta_pct: float) -> str:
    if delta_pct <= -1.0:
        return "Bullish — queda >1% WoW nos estoques"
    if delta_pct >= 1.0:
        return "Bearish — aumento >1% WoW nos estoques"
    return "Estável — sem sinal claro"


def interpret_gas(storage_bcf, delta_bcf, hist_avg=None) -> str:
    if storage_bcf is None:
        return "Sem dados"
    if hist_avg is not None and storage_bcf < hist_avg * 0.9:
        return "Risco de tightness — níveis abaixo da média histórica"
    if delta_bcf < -5:
        return "Atenção: saída semanal forte (-5 Bcf ou mais)"
    return "Normal"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crude", required=True)
    parser.add_argument("--products", required=True)
    parser.add_argument("--gas", required=True)
    parser.add_argument("--out-crude", required=True)
    parser.add_argument("--out-products", required=True)
    parser.add_argument("--out-gas", required=True)
    args = parser.parse_args()

    df_crude = pd.read_csv(args.crude)
    df_products = pd.read_csv(args.products)
    df_gas = pd.read_csv(args.gas)

    # garantir datetime
    for df in (df_crude, df_products, df_gas):
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

    crude_stats = latest_stats(df_crude, "value")
    products_stats = latest_stats(df_products, "value")
    gas_stats = latest_stats(df_gas, "storage_bcf")

    # mensagens
    msg_crude = (
        f"📦 *ENERGY — Petroleum (Crude) Weekly*\n\n"
        f"🔖 *Série:* {crude_stats['label']} ({crude_stats['series_id']})\n"
        f"📅 *Data:* {crude_stats['date']}\n"
        f"📈 *Estoque:* {crude_stats['value']:,.0f} bbl\n"
        f"🔁 *Variação WoW:* {crude_stats['delta']:+,.0f} bbl ({crude_stats['pct']:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interpret_petroleum(crude_stats['pct'])}\n\n"
        f"🔗 Dados: local\n"
    )

    msg_products = (
        f"🛢️ *ENERGY — Petroleum (Crude + Products) Weekly*\n\n"
        f"🔖 *Série:* {products_stats['label']} ({products_stats['series_id']})\n"
        f"📅 *Data:* {products_stats['date']}\n"
        f"📈 *Estoque Total:* {products_stats['value']:,.0f} bbl\n"
        f"🔁 *Variação WoW:* {products_stats['delta']:+,.0f} bbl ({products_stats['pct']:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interpret_petroleum(products_stats['pct'])}\n\n"
        f"🔗 Dados: local\n"
    )

    msg_gas = (
        f"⛽ *ENERGY — Gas Storage Weekly*\n\n"
        f"🔖 *Série:* {gas_stats['label']} ({gas_stats['series_id']})\n"
        f"📅 *Data:* {gas_stats['date']}\n"
        f"📦 *Storage Total:* {gas_stats['value']:,.1f} Bcf\n"
        f"🔁 *Variação WoW:* {gas_stats['delta']:+.1f} Bcf ({gas_stats['pct']:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interpret_gas(gas_stats['value'], gas_stats['delta'])}\n\n"
        f"🔗 Dados: local\n"
    )

    # grava
    with open(args.out_crude, "w", encoding="utf-8") as f:
        f.write(msg_crude)
    with open(args.out_products, "w", encoding="utf-8") as f:
        f.write(msg_products)
    with open(args.out_gas, "w", encoding="utf-8") as f:
        f.write(msg_gas)

    print("WROTE telegram messages")


if __name__ == "__main__":
    main()
