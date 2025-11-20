#!/usr/bin/env python3
"""
Formata 3 mensagens Telegram (uma por ativo) a partir dos CSVs:

 - crude:      /tmp/petroleum_crude.csv
 - products:   /tmp/petroleum_products.csv
 - gas:        /tmp/gas_storage.csv

Gera 3 arquivos de texto:

 - /tmp/telegram_petroleum_crude.txt
 - /tmp/telegram_petroleum_products.txt
 - /tmp/telegram_gas_storage.txt
"""

import argparse
from datetime import datetime
import pandas as pd


def latest_stats(df: pd.DataFrame, value_col: str = "value"):
    if df is None or len(df) == 0:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else None

    date_latest = pd.to_datetime(latest["date"]).date()
    val_latest = float(latest[value_col]) if pd.notna(latest[value_col]) else None

    if prev is not None and pd.notna(prev[value_col]) and val_latest is not None:
        prev_val = float(prev[value_col])
        delta = val_latest - prev_val
        pct = (delta / prev_val) * 100 if prev_val != 0 else 0.0
    else:
        delta = 0.0
        pct = 0.0

    return {
        "date": date_latest,
        "value": val_latest,
        "delta": delta,
        "pct": pct,
        "label": latest.get("label", ""),
        "series_id": latest.get("series_id", ""),
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


def format_petroleum_msg(stats, dataset_link=None) -> str:
    if stats is None:
        return "📦 *ENERGY — Petroleum (Crude)*\n\nSem dados disponíveis."

    date = stats["date"]
    v = stats["value"]
    d = stats["delta"]
    p = stats["pct"]
    label = stats["label"]
    sid = stats["series_id"]
    interp = interpret_petroleum(p)

    return (
        f"📦 *ENERGY — Petroleum (Crude) Weekly*\n\n"
        f"🔖 *Série:* {label} ({sid})\n"
        f"📅 *Data:* {date}\n"
        f"📈 *Estoque:* {v:,.0f} bbl\n"
        f"🔁 *Variação WoW:* {d:+,.0f} bbl ({p:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interp}\n\n"
        f"🔗 Dados: {dataset_link or 'local'}\n"
    )


def format_products_msg(stats, dataset_link=None) -> str:
    if stats is None:
        return "🛢️ *ENERGY — Petroleum (Crude + Products)*\n\nSem dados disponíveis."

    date = stats["date"]
    v = stats["value"]
    d = stats["delta"]
    p = stats["pct"]
    label = stats["label"]
    sid = stats["series_id"]
    interp = interpret_petroleum(p)

    return (
        f"🛢️ *ENERGY — Petroleum (Crude + Products) Weekly*\n\n"
        f"🔖 *Série:* {label} ({sid})\n"
        f"📅 *Data:* {date}\n"
        f"📈 *Estoque Total:* {v:,.0f} bbl\n"
        f"🔁 *Variação WoW:* {d:+,.0f} bbl ({p:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interp}\n\n"
        f"🔗 Dados: {dataset_link or 'local'}\n"
    )


def format_gas_msg(stats, dataset_link=None, hist_avg=None) -> str:
    if stats is None:
        return "⛽ *ENERGY — Gas Storage Weekly*\n\nSem dados disponíveis."

    date = stats["date"]
    v = stats.get("value")
    d = stats.get("delta")
    p = stats.get("pct")
    label = stats.get("label", "")
    sid = stats.get("series_id", "")
    interp = interpret_gas(v, d, hist_avg)

    return (
        f"⛽ *ENERGY — Gas Storage Weekly*\n\n"
        f"🔖 *Série:* {label} ({sid})\n"
        f"📅 *Data:* {date}\n"
        f"📦 *Storage Total:* {v:,.1f} Bcf\n"
        f"🔁 *Variação WoW:* {d:+,.1f} Bcf ({p:+.2f}%)\n\n"
        f"🔍 *Interpretação rápida:* {interp}\n\n"
        f"🔗 Dados: {dataset_link or 'local'}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crude", required=True)
    parser.add_argument("--products", required=True)
    parser.add_argument("--gas", required=True)
    parser.add_argument("--out-crude", required=True)
    parser.add_argument("--out-products", required=True)
    parser.add_argument("--out-gas", required=True)
    parser.add_argument("--hist-gas-avg", type=float, default=None)
    parser.add_argument("--dataset-link", default=None)
    args = parser.parse_args()

    df_crude = pd.read_csv(args.crude)
    df_products = pd.read_csv(args.products)
    df_gas = pd.read_csv(args.gas)

    for df in (df_crude, df_products, df_gas):
        if "date" in df.columns:
            try:
                df["date"] = pd.to_datetime(df["date"])
            except Exception:
                pass

    s_crude = latest_stats(df_crude, "value") if len(df_crude) > 0 else None
    s_products = latest_stats(df_products, "value") if len(df_products) > 0 else None

    gas_col = "storage_bcf" if "storage_bcf" in df_gas.columns else "value"
    s_gas = latest_stats(df_gas, gas_col) if len(df_gas) > 0 else None

    msg_crude = format_petroleum_msg(s_crude, dataset_link=args.dataset_link)
    msg_products = format_products_msg(s_products, dataset_link=args.dataset_link)
    msg_gas = format_gas_msg(s_gas, dataset_link=args.dataset_link, hist_avg=args.hist_gas_avg)

    with open(args.out_crude, "w", encoding="utf-8") as f:
        f.write(msg_crude)
    with open(args.out_products, "w", encoding="utf-8") as f:
        f.write(msg_products)
    with open(args.out_gas, "w", encoding="utf-8") as f:
        f.write(msg_gas)

    print("WROTE", args.out_crude, args.out_products, args.out_gas)


if __name__ == "__main__":
    main()
