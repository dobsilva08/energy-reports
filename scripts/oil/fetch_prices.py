import os
import requests

def _get_price(symbol):
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key:
        print("Alpha Vantage key missing; oil price unavailable.")
        return None
    url = f"https://www.alphavantage.co/query?function={symbol}&apikey={key}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        rows = data.get("data")
        if rows and rows[0].get("value") not in (None, ""):
            return float(rows[0]["value"])
        # Avoid treating API throttling/errors as prices.
        print(f"Alpha Vantage {symbol} unavailable: {data.get('Note') or data.get('Information') or data.get('Error Message') or 'unexpected response'}")
    except Exception as exc:
        print(f"Oil price fetch {symbol} failed: {exc}")
    return None

def get_wti_price():
    return _get_price("WTI")

def get_brent_price():
    return _get_price("BRENT")
