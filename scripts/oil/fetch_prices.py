import os
import requests


def get_wti_price():
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    url = f"https://www.alphavantage.co/query?function=WTI&apikey={key}"
    r = requests.get(url, timeout=30)
    data = r.json()
    return float(data["data"][0]["value"])


def get_brent_price():
    key = os.getenv("ALPHA_VANTAGE_API_KEY")
    url = f"https://www.alphavantage.co/query?function=BRENT&apikey={key}"
    r = requests.get(url, timeout=30)
    data = r.json()
    return float(data["data"][0]["value"])
