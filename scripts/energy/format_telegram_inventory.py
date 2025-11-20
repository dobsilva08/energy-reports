#!/usr/bin/env python3
import argparse
import pandas as pd
from datetime import datetime


# Nome oficial das séries (fallback FINAL garantido)
SERIES_NAMES = {
    "PET.WCESTUS1.W": "Weekly U.S. Ending Stocks of Crude Oil (Excluding SPR)",
    "PET.WTTSTUS1.W": "Weekly U.S. Total Stocks of Crude Oil & Petroleum Products",
    "NG.NW2_EPG0_SWO_R48_BCF.W": "Working Gas in Underground Storage — Lower 48 States",
}


def clean_label(label):
    """Converte nan/None/'nan'/'None'/'' para None."""
    if label is None:
        return None
    if isinstance(label, float) and pd.isna(label):
        return None
    if isinstance(label, str):
        l = label.strip().lower()
        if l in ("", "nan", "none", "null"):
            return None
    return label


def resolve_series_name(series_id, raw_label):
    """
    Retorna:
    1) label vindo da API (se existir)
    2) fallback oficial do nosso dicionário
    3) fallback genérico "Série {id}"
    """
    cleaned = clean_label(raw_label)
    if cleaned:
        return cleaned

    if series_id in SERIES_NAMES:
        return SERIES_NAMES[series_id]

    return f"Série {series_id}"


def latest_stats(df: pd.DataFrame, value_col: str = "value"):
    if df is None or len(df) == 0:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None

    series_id = latest.get("series_id")
    raw_label = latest.get("label")
    series_label = resolve_series_name(series_id, raw_label)

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
        "label": series_label,
        "series_id": series_id,
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

    # Garantir datetime
    for df in (df_crude, df_products, df_gas):
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

    crude_stats = latest_stats(df_crude)
    products_stats = latest_stats(df_products)
    gas_stats = latest_stats(df_gas, value_col="storage_bcf")

    # CRUDE
    msg_crude = (
        f"📦 *ENERGY — Petroleum (Crude) Weekly*\n\n"
        f"🔖 *Série:* {crude_stats['label']} ({crude_stats['series_id']})\n"
        f"📅 *Data:* {crude_stats['date']}\n"
        f"📈 *Estoque:* {crude_stats['value']:,.0f} bbl\n"
        f"🔁 *Variação WoW:* {crude_stats['delta']:+,.0f} bbl ({crude_stats['pct']:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interpret_petroleum(crude_stats['pct'])}\n\n"
        f"🔗 Dados: local\n"
    )

    # PRODUCTS
    msg_products = (
        f"🛢️ *ENERGY — Petroleum (Crude + Products) Weekly*\n\n"
        f"🔖 *Série:* {products_stats['label']} ({products_stats['series_id']})\n"
        f"📅 *Data:* {products_stats['date']}\n"
        f"📈 *Estoque Total:* {products_stats['value']:,.0f} bbl\n"
        f"🔁 *Variação WoW:* {products_stats['delta']:+,.0f} bbl ({products_stats['pct']:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interpret_petroleum(products_stats['pct'])}\n\n"
        f"🔗 Dados: local\n"
    )

    # GAS
    msg_gas = (
        f"⛽ *ENERGY — Gas Storage Weekly*\n\n"
        f"🔖 *Série:* {gas_stats['label']} ({gas_stats['series_id']})\n"
        f"📅 *Data:* {gas_stats['date']}\n"
        f"📦 *Storage Total:* {gas_stats['value']:,.1f} Bcf\n"
        f"🔁 *Variação WoW:* {gas_stats['delta']:+.1f} Bcf ({gas_stats['pct']:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interpret_gas(gas_stats['value'], gas_stats['delta'])}\n\n"
        f"🔗 Dados: local\n"
    )

    with open(args.out_crude, "w", encoding="utf-8") as f:
        f.write(msg_crude)
    with open(args.out_products, "w", encoding="utf-8") as f:
        f.write(msg_products)
    with open(args.out_gas, "w", encoding="utf-8") as f:
        f.write(msg_gas)

    print("WROTE telegram messages")


if __name__ == "__main__":
    main()
