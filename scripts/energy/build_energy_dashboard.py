#!/usr/bin/env python3
"""
Gera um dashboard em Markdown para o Energy Weekly.

Entradas:
 - crude csv:    /tmp/petroleum_crude.csv
 - products csv: /tmp/petroleum_products.csv
 - gas csv:      /tmp/gas_storage.csv
 - summary txt:  /tmp/telegram_energy_summary.txt

Saída:
 - /tmp/energy_dashboard/energy_weekly_dashboard.md
"""

import argparse
import pandas as pd
from datetime import datetime


def latest_stats(df: pd.DataFrame, value_col: str):
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--crude", required=True)
    p.add_argument("--products", required=True)
    p.add_argument("--gas", required=True)
    p.add_argument("--summary", required=True)
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

    with open(args.summary, "r", encoding="utf-8") as f:
        summary_text = f.read()

    ref_date = crude_stats["date"] if crude_stats else None

    lines = []

    # Cabeçalho
    lines.append(f"# 📊 Energy Weekly Dashboard")
    if ref_date:
        lines.append(f"**Referência semanal:** {ref_date}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Visão rápida numérica
    lines.append("## 1. Visão rápida — Números principais")
    lines.append("")
    if crude_stats:
        lines.append(
            f"- **Crude (Ex-SPR)**: {crude_stats['value']:,.0f} bbl  "
            f"({crude_stats['delta']:+,.0f} bbl WoW, {crude_stats['pct']:+.2f}%)"
        )
    if products_stats:
        lines.append(
            f"- **Crude + Products (Total US)**: {products_stats['value']:,.0f} bbl  "
            f"({products_stats['delta']:+,.0f} bbl WoW, {products_stats['pct']:+.2f}%)"
        )
    if gas_stats:
        lines.append(
            f"- **Gas Storage (Lower 48)**: {gas_stats['value']:,.1f} Bcf  "
            f"({gas_stats['delta']:+.1f} Bcf WoW, {gas_stats['pct']:+.2f}%)"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Macro summary (o mesmo que vai para o Telegram)
    lines.append("## 2. Leitura macro da semana")
    lines.append("")
    lines.append("```text")
    lines.append(summary_text.strip())
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Gráficos
    lines.append("## 3. Gráficos")
    lines.append("")
    lines.append("### 3.1 Crude Inventories — últimas 12 semanas")
    lines.append("![Crude 12w](crude_12w.png)")
    lines.append("")
    lines.append("### 3.2 Crude + Products — Total US — últimas 12 semanas")
    lines.append("![Crude+Products 12w](products_12w.png)")
    lines.append("")
    lines.append("### 3.3 Gas Storage — Lower 48 — últimas 12 semanas")
    lines.append("![Gas 12w](gas_12w.png)")
    lines.append("")
    lines.append("### 3.4 Gas Storage — ano atual vs média 5 anos")
    lines.append("![Gas vs 5y](gas_vs_5y.png)")
    lines.append("")
    lines.append("### 3.5 Crude Seasonality — últimos 5 anos")
    lines.append("![Crude Seasonality 5y](crude_seasonality_5y.png)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Observações técnicas
    lines.append("## 4. Notas técnicas")
    lines.append("")
    lines.append("- Fonte: U.S. EIA (API v2, séries PET.WCESTUS1.W, PET.WTTSTUS1.W, NG.NW2_EPG0_SWO_R48_BCF.W).")
    lines.append("- Todos os valores são aproximados; podem existir revisões posteriores da EIA.")
    lines.append("- Cálculos WoW e tendência são feitos automaticamente pelo pipeline Energy Reports.")
    lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("WROTE", args.out)


if __name__ == "__main__":
    main()
