# scripts/oil/fetch_prices.py
import os
import time
import requests
from typing import Dict
import random

ALPHA_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
NASDAQ_KEY = os.environ.get("NASDAQ_DATA_LINK_API_KEY", "").strip()

def _mock_prices() -> Dict[str, float]:
    # deterministic-ish random for dev
    wti = round(70 + random.random()*10, 2)
    brent = round(wti + random.uniform(-3, 5), 2)
    return {"wti": wti, "brent": brent, "spread": round(brent - wti, 2)}

def _alpha_vantage_fx(symbol: str) -> float:
    """
    Attempt to get price via AlphaVantage. For oil you might query a commodity symbol or use a custom data source.
    This is a generic example; adapt to your premium provider if needed.
    """
    if not ALPHA_KEY:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY not set")
    # Example endpoint - Alpha Vantage free APIs primarily focus on FX/stocks - this is illustrative.
    url = "https://www.alphavantage.co/query"
    params = {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol, "apikey": ALPHA_KEY, "outputsize": "compact"}
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError("AlphaVantage request failed")
    data = resp.json()
    ts = data.get("Time Series (Daily)", {})
    if not ts:
        raise RuntimeError("AlphaVantage returned no time series")
    latest = next(iter(ts.values()))
    # Adjust depending on provider: here we take '4. close'
    close = float(latest.get("4. close", 0.0))
    return close

def fetch_prices() -> Dict[str, float]:
    """
    Returns dict: {'wti': float, 'brent': float, 'spread': float}
    """
    # Try primary source: AlphaVantage (if you have commodity symbols configured)
    try:
        if ALPHA_KEY:
            # You need to configure which symbols you use for WTI/Brent in your data provider.
            # Placeholder: try retrieving fallback symbols; adjust to real symbols for your account.
            # Examples: 'CL=F' (Yahoo style) will not work on AlphaVantage free tier. Replace if you have paid feed.
            wti = _alpha_vantage_fx("WTI")    # <- replace with correct mapping
            brent = _alpha_vantage_fx("BRENT")  # <- replace
            return {"wti": round(wti, 2), "brent": round(brent, 2), "spread": round(brent - wti, 2)}
    except Exception as e:
        # fail silently to fallback
        print("alpha fetch failed:", e)

    # Try NASDAQ Data Link if key present (example)
    if NASDAQ_KEY:
        try:
            # Example: use Nasdaq Data Link API if you have dataset for CL/BZ.
            # Adapt dataset path to your purchased dataset.
            # Placeholder request: not implemented concretely here—user to adapt.
            pass
        except Exception as e:
            print("nasdaq fetch failed:", e)

    # Final fallback: mock prices (safe)
    print("Using mock prices (fallback)")
    return _mock_prices()
