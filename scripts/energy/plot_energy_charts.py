#!/usr/bin/env python3
"""
Gera gráficos em PNG para os relatórios semanais de energia:

Entradas (CSV, já gerados pelo fetch_and_parse_eia.py):
 - crude:    /tmp/petroleum_crude.csv
 - products: /tmp/petroleum_products.csv
 - gas:      /tmp/gas_storage.csv

Saídas (PNG):
 - /tmp/crude_12w.png
 - /tmp/products_12w.png
 - /tmp/gas_12w.png
"""

import argparse
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt


def prepare_df(path: str, value_col: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError(f"CSV {path} não possui coluna 'date'")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    if value_col not in df.columns:
        raise ValueError(f"CSV {path} não possui coluna '{value_col}'")

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df = df.dropna(subset=[value_col])

    # pega só as últimas 12 semanas
    if len(df) > 12:
        df = df.tail(12)

    return df


def plot_line(df: pd.DataFrame, date_col: str, value_col: str, title: str, ylabel: str, outfile: str):
    plt.figure(figsize=(10, 4))
    plt.plot(df[date_col], df[value_col], marker="o")
    plt.title(title)
    plt.xlabel("Semana")
    plt.ylabel(ylabel)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()
    print("WROTE", outfile)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--crude", required=True)
    p.add_argument("--products", required=True)
    p.add_argument("--gas", required=True)
    p.add_argument("--out-crude", required=True)
    p.add_argument("--out-products", required=True)
    p.add_argument("--out-gas", required=True)
    args = p.parse_args()

    # Crude
    df_crude = prepare_df(args.crude, "value")
    plot_line(
        df_crude,
        "date",
        "value",
        "Crude Inventories (Ex-SPR) — últimas 12 semanas",
        "Milhões de barris (aprox.)",
        args.out_crude,
    )

    # Products (Total)
    df_products = prepare_df(args.products, "value")
    plot_line(
        df_products,
        "date",
        "value",
        "Crude + Products — Total US — últimas 12 semanas",
        "Milhões de barris (aprox.)",
        args.out_products,
    )

    # Gas Storage
    df_gas = prepare_df(args.gas, "storage_bcf")
    plot_line(
        df_gas,
        "date",
        "storage_bcf",
        "Gas Storage — Lower 48 — últimas 12 semanas",
        "Bcf",
        args.out_gas,
    )


if __name__ == "__main__":
    main()
