import os
import json
import argparse
import requests
import time
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Variáveis de ambiente
# ------------------------------------------------------------------
FRED_API_KEY = os.getenv("FRED_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID_ENERGY = os.getenv("TELEGRAM_CHAT_ID_ENERGY")

if FRED_API_KEY is None:
    raise RuntimeError("FRED_API_KEY não encontrado nas variáveis de ambiente.")
if TELEGRAM_BOT_TOKEN is None or TELEGRAM_CHAT_ID_ENERGY is None:
    raise RuntimeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID_ENERGY não configurados.")

# ------------------------------------------------------------------
# Telegram
# ------------------------------------------------------------------
def telegram_send_message(text: str) -> None:
    # Plain text, split into safe chunks to prevent HTML parsing/length HTTP 400.
    plain = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("**", "").replace("__", "")
    chunks=[]
    while plain:
        if len(plain)<=3900:
            chunks.append(plain); break
        cut=plain.rfind("\\n",0,3900)
        if cut<1900: cut=3900
        chunks.append(plain[:cut]); plain=plain[cut:].lstrip()
    url=f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chunk in chunks:
        payload={"chat_id":TELEGRAM_CHAT_ID_ENERGY,"text":chunk,"disable_web_page_preview":True}
        r=requests.post(url,json=payload,timeout=30);r.raise_for_status()
        data=r.json()
        if not data.get("ok",False): raise RuntimeError(f"Telegram API error: {data}")
    print(f"Telegram sent ({len(chunks)} message(s)).")

