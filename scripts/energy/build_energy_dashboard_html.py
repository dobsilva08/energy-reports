#!/usr/bin/env python3
"""
Gera um dashboard HTML para o Energy Weekly, com visão numérica,
macro summary, gráficos e um módulo simples de "forecast & alerts".

Entradas:
 - crude csv:    /tmp/petroleum_crude.csv
 - products csv: /tmp/petroleum_products.csv
 - gas csv:      /tmp/gas_storage.csv
 - summary txt:  /tmp/telegram_energy_summary.txt

Saída:
 - /tmp/energy_dashboard/energy_weekly_dashboard.html
"""

import argparse
from datetime import datetime
import numpy as np
import pandas as pd


def latest_stats(df: pd.DataFrame, value_col: str, max_hist_weeks: int = 60):
    df = df.sort_values("date").reset_index(drop=True)
    if len(df) == 0:
        return None, None

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

    # série de variações semanais para "ML light"
    df = df.tail(max_hist_weeks + 1).copy()
    df["val"] = pd.to_numeric(df[value_col], errors="coerce")
    df["delta_w"] = df["val"].diff()

    changes = df["delta_w"].dropna().values
    hist = {"changes": changes} if len(changes) > 0 else {"changes": np.array([])}

    return {
        "date": date_latest,
        "value": v_latest,
        "delta": delta,
        "pct": pct,
    }, hist


def compute_forecast_and_zscore(series_hist):
    """
    Recebe o dict com "changes" (últimas deltas semanais).
    Retorna z-score da última delta e parâmetros de regressão
    simples para uma tendência de curto prazo.
    """
    changes = series_hist["changes"]
    if changes.size < 8:
        return {"zscore": None, "is_outlier": False, "trend_slope": None, "forecast_4w": None}

    # z-score do último move
    last_change = changes[-1]
    mean = changes.mean()
    std = changes.std(ddof=1) if changes.size > 1 else 0.0
    z = (last_change - mean) / std if std not in (0.0, np.nan) else 0.0
    is_outlier = abs(z) >= 2.0

    # regressão linear simples dos valores acumulados
    # (se quiser algo mais robusto no futuro, dá para trocar por ARIMA, etc.)
    idx = np.arange(len(changes))
    slope, intercept = np.polyfit(idx, changes, 1)
    # forecast simples: soma das próximas 4 semanas de "delta"
    future_idx = np.arange(len(changes), len(changes) + 4)
    forecast_changes = slope * future_idx + intercept
    forecast_4w = forecast_changes.sum()

    return {
        "zscore": float(z),
        "is_outlier": bool(is_outlier),
        "trend_slope": float(slope),
        "forecast_4w": float(forecast_4w),
        "last_change": float(last_change),
    }


def describe_alert(name: str, stats, ml):
    if stats is None:
        return f"<li><b>{name}</b>: sem dados suficientes.</li>"

    delta = stats["delta"]
    pct = stats["pct"]
    z = ml["zscore"]
    outlier = ml["is_outlier"]
    forecast_4w = ml["forecast_4w"]

    txt = f"<li><b>{name}</b>: Δ semanal {delta:+,.0f} ({pct:+.2f}%). "
    if z is not None:
        txt += f"z-score da variação semanal: {z:+.2f}. "
        if outlier:
            txt += "<b>Movimento fora do padrão histórico (outlier estatístico).</b> "
    if forecast_4w is not None:
        if forecast_4w < 0:
            txt += f"Tendência de curto prazo sugere queda agregada de {forecast_4w:,.0f} unidades nas próximas 4 semanas."
        elif forecast_4w > 0:
            txt += f"Tendência de curto prazo sugere alta agregada de {forecast_4w:,.0f} unidades nas próximas 4 semanas."
        else:
            txt += "Tendência de curto prazo praticamente neutra para as próximas 4 semanas."
    txt += "</li>"
    return txt


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

    crude_stats, crude_hist = latest_stats(df_crude, "value")
    products_stats, products_hist = latest_stats(df_products, "value")
    gas_stats, gas_hist = latest_stats(df_gas, "storage_bcf")

    crude_ml = compute_forecast_and_zscore(crude_hist)
    products_ml = compute_forecast_and_zscore(products_hist)
    gas_ml = compute_forecast_and_zscore(gas_hist)

    with open(args.summary, "r", encoding="utf-8") as f:
        summary_text = f.read()

    ref_date = crude_stats["date"] if crude_stats else None

    # HTML simples, mas organizado
    html = []

    html.append("<!DOCTYPE html>")
    html.append("<html lang='en'>")
    html.append("<head>")
    html.append("<meta charset='utf-8'/>")
    html.append("<title>Energy Weekly Dashboard</title>")
    html.append(
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
        "background:#0d1117;color:#e6edf3;margin:0;padding:0;}"
        "h1,h2,h3{color:#e6edf3;margin-bottom:0.4rem;}"
        "a{color:#58a6ff;}"
        ".container{max-width:1100px;margin:0 auto;padding:24px;}"
        ".card{background:#161b22;border-radius:12px;padding:16px 20px;margin-bottom:16px;"
        "box-shadow:0 0 0 1px #30363d;}"
        ".badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;"
        "background:#238636;color:#fff;margin-left:6px;}"
        "table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px;}"
        "th,td{border-bottom:1px solid #30363d;padding:6px 4px;text-align:right;}"
        "th:first-child,td:first-child{text-align:left;}"
        "img{max-width:100%;border-radius:10px;border:1px solid #30363d;margin-top:4px;}"
        "code{font-family:Menlo,Consolas,monospace;font-size:12px;white-space:pre-wrap;}"
        "ul{margin-top:4px;margin-bottom:4px;padding-left:18px;}"
        "</style>"
    )
    html.append("</head>")
    html.append("<body>")
    html.append("<div class='container'>")

    # Header
    html.append("<div class='card'>")
    html.append("<h1>📊 Energy Weekly Dashboard<span class='badge'>Auto-generated</span></h1>")
    if ref_date:
        html.append(f"<p><b>Referência semanal:</b> {ref_date}</p>")
    html.append("<p>Resumo consolidado de estoques de petróleo (crude & products) e gas storage nos EUA, com foco em variações semanais, "
                "tendência de curto prazo e contexto sazonal.</p>")
    html.append("</div>")

    # Tabela de números
    html.append("<div class='card'>")
    html.append("<h2>1. Visão rápida — números principais</h2>")
    html.append("<table>")
    html.append("<thead><tr><th>Série</th><th>Nível</th><th>Δ WoW</th><th>% WoW</th></tr></thead>")
    html.append("<tbody>")
    if crude_stats:
        html.append(
            f"<tr><td>Crude (Ex-SPR)</td>"
            f"<td>{crude_stats['value']:,.0f}</td>"
            f"<td>{crude_stats['delta']:+,.0f}</td>"
            f"<td>{crude_stats['pct']:+.2f}%</td></tr>"
        )
    if products_stats:
        html.append(
            f"<tr><td>Crude + Products (Total US)</td>"
            f"<td>{products_stats['value']:,.0f}</td>"
            f"<td>{products_stats['delta']:+,.0f}</td>"
            f"<td>{products_stats['pct']:+.2f}%</td></tr>"
        )
    if gas_stats:
        html.append(
            f"<tr><td>Gas Storage (Lower 48)</td>"
            f"<td>{gas_stats['value']:,.1f}</td>"
            f"<td>{gas_stats['delta']:+.1f}</td>"
            f"<td>{gas_stats['pct']:+.2f}%</td></tr>"
        )
    html.append("</tbody></table>")
    html.append("</div>")

    # Macro summary (mesmo texto que vai pro Telegram)
    html.append("<div class='card'>")
    html.append("<h2>2. Leitura macro da semana</h2>")
    html.append("<code>")
    html.append(summary_text.replace("<", "&lt;").replace(">", "&gt;"))
    html.append("</code>")
    html.append("</div>")

    # Forecast & Alerts
    html.append("<div class='card'>")
    html.append("<h2>3. Forecast & Alerts (ML light)</h2>")
    html.append("<p>Modelo simples baseado na distribuição histórica das variações semanais (z-score) "
                "e regressão linear das últimas semanas para estimar a direção de curto prazo.</p>")
    html.append("<ul>")
    html.append(describe_alert("Crude (Ex-SPR)", crude_stats, crude_ml))
    html.append(describe_alert("Crude + Products (Total US)", products_stats, products_ml))
    html.append(describe_alert("Gas Storage (Lower 48)", gas_stats, gas_ml))
    html.append("</ul>")
    html.append("</div>")

    # Gráficos
    html.append("<div class='card'>")
    html.append("<h2>4. Gráficos</h2>")

    html.append("<h3>4.1 Crude Inventories — últimas 12 semanas</h3>")
    html.append("<img src='crude_12w.png' alt='Crude 12w'/>")

    html.append("<h3>4.2 Crude + Products — Total US — últimas 12 semanas</h3>")
    html.append("<img src='products_12w.png' alt='Crude+Products 12w'/>")

    html.append("<h3>4.3 Gas Storage — Lower 48 — últimas 12 semanas</h3>")
    html.append("<img src='gas_12w.png' alt='Gas 12w'/>")

    html.append("<h3>4.4 Gas Storage — ano atual vs média 5 anos</h3>")
    html.append("<img src='gas_vs_5y.png' alt='Gas vs 5y'/>")

    html.append("<h3>4.5 Crude Inventories — sazonalidade (últimos 5 anos)</h3>")
    html.append("<img src='crude_seasonality_5y.png' alt='Crude Seasonality 5y'/>")

    html.append("</div>")

    # Rodapé
    html.append("<div class='card'>")
    html.append("<h3>5. Notas técnicas</h3>")
    html.append("<ul>")
    html.append("<li>Fonte: U.S. EIA (API v2, séries PET.WCESTUS1.W, PET.WTTSTUS1.W, NG.NW2_EPG0_SWO_R48_BCF.W).</li>")
    html.append("<li>Variações e tendências são calculadas automaticamente a partir das séries semanais.</li>")
    html.append("<li>Forecast & Alerts utiliza apenas métodos estatísticos simples; não substitui modelos de previsão estruturais.</li>")
    html.append("</ul>")
    html.append("</div>")

    html.append("</div></body></html>")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

    print("WROTE", args.out)


if __name__ == "__main__":
    main()
