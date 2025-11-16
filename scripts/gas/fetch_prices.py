# scripts/gas/fetch_prices.py
"""
Fetch prices for Natural Gas (Henry Hub).
Priority:
 - EIA (if EIA_API_KEY set)
 - AlphaVantage (if ALPHA_VANTAGE_API_KEY set) [may require custom mapping]
 - NASDAQ Data Link (if NASDAQ_DATA_LINK_API_KEY set) - placeholder
 - Fallback: mock prices
"""

import os
import time
import requests
import random
from typing import Dict

EIA_KEY = os.environ.get("EIA_API_KEY", "").strip()
ALPHA_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
NASDAQ_KEY = os.environ.get("NASDAQ_DATA_LINK_API_KEY", "").strip()
FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()

def _mock_prices() -> Dict[str, float]:
    # deterministic-ish mock for development
    base = 3.5 + random.random() * 2.5
    hub = round(base, 3)           # Henry Hub (USD/MMBtu)
    front_month = round(base + random.uniform(-0.2, 0.2), 3)
    spot = hub
    return {"henry_hub_spot": spot, "front_month": front_month, "unit": "USD/MMBtu"}

def fetch_from_eia() -> Dict[str, float]:
    """
    Try EIA API (Natural Gas Weekly or Daily). Example endpoint:
    https://api.eia.gov/series/?api_key=YOUR_KEY&series_id=NG.RNGWHHD.D
    (That series id is just illustrative; user must adapt to their dataset)
    """
    if not EIA_KEY:
        raise RuntimeError("EIA_API_KEY not set")
    # Example: weekly Henry Hub spot price series id in EIA: NATURAL GAS SPOT PRICE??
    # This is illustrative — adapt series_id to the one you have access to.
    series_id = os.getenv("EIA_SERIES_ID", "NG.RNGWHHD.D")  # fallback placeholder
    url = "https://api.eia.gov/series/"
    params = {"api_key": EIA_KEY, "series_id": series_id}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    series = data.get("series", [])
    if not series:
        raise RuntimeError("EIA returned empty series")
    # series[0]['data'] is list of [date, value], newest first typically
    latest = series[0].get("data", [])[0]
    value = float(latest[1])
    return {"henry_hub_spot": round(value, 3), "front_month": round(value, 3), "unit": "USD/MMBtu"}

def fetch_from_alpha() -> Dict[str, float]:
    """
    AlphaVantage placeholder - free tier might not provide commodities.
    Keep as optional fallback if you have a data mapping.
    """
    if not ALPHA_KEY:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY not set")
    # Example: there is no guaranteed 'WTI' style function for NG; this is illustrative.
    # You should replace 'NG_COMMODITY_SYMBOL' with a valid symbol from your provider.
    symbol = os.getenv("ALPHA_NG_SYMBOL", "NG=F")
    url = "https://www.alphavantage.co/query"
    params = {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol, "apikey": ALPHA_KEY, "outputsize": "compact"}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    j = r.json()
    ts = j.get("Time Series (Daily)", {})
    if not ts:
        raise RuntimeError("AlphaVantage returned no time series for symbol")
    latest = next(iter(ts.values()))
    close = float(latest.get("4. close", 0.0))
    return {"henry_hub_spot": round(close, 3), "front_month": round(close, 3), "unit": "USD/MMBtu"}

def fetch_from_nasdaq() -> Dict[str, float]:
    """
    Placeholder for Nasdaq Data Link (formerly Quandl / Nasdaq Data Link).
    Implement dataset path if you have access.
    """
    if not NASDAQ_KEY:
        raise RuntimeError("NASDAQ_DATA_LINK_API_KEY not set")
    # Implement according to your dataset; here we raise to force fallback
    raise RuntimeError("NASDAQ dataset not configured in fetch_from_nasdaq")

def fetch_prices() -> Dict[str, float]:
    """
    Return dict: {'henry_hub_spot': float, 'front_month': float, 'unit': 'USD/MMBtu'}
    Will attempt providers in order and fallback to mock.
    """
    # Try EIA
    try:
        if EIA_KEY:
            return fetch_from_eia()
    except Exception as e:
        print("EIA fetch failed:", e)

    # Try Alpha
    try:
        if ALPHA_KEY:
            return fetch_from_alpha()
    except Exception as e:
        print("Alpha fetch failed:", e)

    # Try Nasdaq Data Link
    try:
        if NASDAQ_KEY:
            return fetch_from_nasdaq()
    except Exception as e:
        print("Nasdaq fetch failed:", e)

    # Try FRED for related series (optional)
    try:
        if FRED_KEY:
            # Example: you can fetch natural gas series from FRED if you have mapping
            # Placeholder: not implemented; user can extend.
            pass
    except Exception as e:
        print("FRED fetch failed:", e)

    # Final fallback: mock
    print("Using mock gas prices (fallback)")
    return _mock_prices()

