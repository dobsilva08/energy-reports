#!/usr/bin/env python3
"""
Gera gráficos em PNG para os relatórios semanais de energia.

Entradas (CSV, já gerados pelo fetch_and_parse_eia.py):
 - crude:    /tmp/petroleum_crude.csv
 - products: /tmp/petroleum_products.csv
 - gas:      /tmp/gas_storage.csv

Saídas (PNG):
 - /tmp/crude_12w.png
 - /tmp/products_12w.png
 - /tmp/gas_12w.png
 - /tmp/gas_vs_5y.png
 - /tmp/crude_seasonality_5y.png
"""

import argparse
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt


def _base_style():
    """Ajusta estilo básico (tipo 'banco', mas sem mexer em cores diretamente)."""
    plt.style.use("default")
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["grid.alpha"] = 0.3
    plt.rcParams["figure.figsize"] = (10, 4)


def prepare_df_full(path: str, value_col: str) -> pd.DataFrame:
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
    return df


def prepare_df_12w(path: str, value_col: str) -> pd.DataFrame:
    df = prepare_df_full(path, value_col)
    if len(df) > 12:
        df = df.tail(12)
    return df


def plot_line(df: pd.DataFrame, date_col: str, value_col: str, title: str, ylabel: str, outfile: str):
    _base_style()
    plt.figure()
    plt.plot(df[date_col], df[value_col], marker="o", linewidth=2)
    plt.title(title)
    plt.xlabel("Semana")
    plt.ylabel(ylabel)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()
    print("WROTE", outfile)


def plot_gas_vs_5y(df_gas: pd.DataFrame, outfile: str):
    """
    Plota Gas Storage atual vs média 5 anos (por semana do ano).
    - Linha 1: ano corrente
    - Linha 2: média das últimas 5 safras anteriores
    """
    _base_style()
    df = df_gas.copy()
    df["year"] = df["date"].dt.year
    df["week"] = df["date"].dt.isocalendar().week.astype(int)

    current_year = df["year"].max()
    prev_years = [y for y in range(current_year - 5, current_year) if y in df["year"].unique()]

    df_curr = df[df["year"] == current_year]
    df_prev = df[df["year"].isin(prev_years)]

    if df_prev.empty or df_curr.empty:
        print("WARN: dados insuficientes para gas_vs_5y, pulando gráfico")
        return

    mean_prev = df_prev.groupby("week")["storage_bcf"].mean().reset_index(name="storage_mean")
    merged = pd.merge(df_curr[["date", "week", "storage_bcf"]], mean_prev, on="week", how="left")

    plt.figure()
    plt.plot(merged["date"], merged["storage_bcf"], marker="o", linewidth=2, label=f"{current_year} (atual)")
    plt.plot(merged["date"], merged["storage_mean"], linestyle="--", linewidth=2, label="Média 5 anos anteriores")
    plt.title("Gas Storage — ano atual vs média 5 anos (por semana)")
    plt.xlabel("Semana")
    plt.ylabel("Bcf")
    plt.xticks(rotation=45, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outfile, dpi=150)
    plt.close()
    print("WROTE", outfile)


def plot_crude_seasonality(df_crude: pd.DataFrame, outfile: str):
    """
    Crude Seasonality (últimos 5 anos) — cada ano como uma linha vs semana do ano.
    """
    _base_style()
    df = df_crude.copy()
    df["year"] = df["date"].dt.year
    df["week"] = df["date"].dt.isocalendar().week.astype(int)

    last_year = df["year"].max()
    years = [y for y in range(last_year - 4, last_year + 1) if y in df["year"].unique()]

    if len(years) < 2:
        print("WARN: dados insuficientes para crude_seasonality_5y, pulando gráfico")
        return

    plt.figure()
    for y in years:
        d = df[df["year"] == y]
        d = d.sort_values("week")
        plt.plot(d["week"], d["value"], linewidth=1.8, marker="o", label=str(y))

    plt.title("Crude Inventories — sazonalidade (últimos 5 anos)")
    plt.xlabel("Semana do ano")
    plt.ylabel("Milhões de barris (aprox.)")
    plt.xticks(rotation=0)
    plt.legend()
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
    p.add_argument("--out-gas-5y", required=True)
    p.add_argument("--out-crude-seasonal", required=True)
    args = p.parse_args()

    # Crude 12w
    df_crude_12 = prepare_df_12w(args.crude, "value")
    plot_line(
        df_crude_12,
        "date",
        "value",
        "Crude Inventories (Ex-SPR) — últimas 12 semanas",
        "Milhões de barris (aprox.)",
        args.out_crude,
    )

    # Products 12w
    df_products_12 = prepare_df_12w(args.products, "value")
    plot_line(
        df_products_12,
        "date",
        "value",
        "Crude + Products — Total US — últimas 12 semanas",
        "Milhões de barris (aprox.)",
        args.out_products,
    )

    # Gas 12w
    df_gas_full = prepare_df_full(args.gas, "storage_bcf")
    df_gas_12 = df_gas_full.copy()
    if len(df_gas_12) > 12:
        df_gas_12 = df_gas_12.tail(12)
    plot_line(
        df_gas_12,
        "date",
        "storage_bcf",
        "Gas Storage — Lower 48 — últimas 12 semanas",
        "Bcf",
        args.out_gas,
    )

    # Gas vs 5-year average
    plot_gas_vs_5y(df_gas_full, args.out_gas_5y)

    # Crude seasonality (5 anos)
    df_crude_full = prepare_df_full(args.crude, "value")
    plot_crude_seasonality(df_crude_full, args.out_crude_seasonal)


if __name__ == "__main__":
    main()
