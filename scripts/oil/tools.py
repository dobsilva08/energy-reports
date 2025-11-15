import os
import json
from datetime import datetime, timezone, timedelta
import requests

BRT = timezone(timedelta(hours=-3))


def ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def today_brt():
    return datetime.now(BRT).strftime("%Y-%m-%d")


def sentinel_trigger(path: str) -> bool:
    """
    Retorna True se já enviou hoje.
    Se não enviou, marca como enviado.
    """
    ensure_dir(path)

    tag = today_brt()

    if os.path.exists(path):
        try:
            data = json.load(open(path, "r"))
            if data.get("last_sent") == tag:
                return True
        except:
            pass

    json.dump({"last_sent": tag}, open(path, "w"))
    return False


def increment_counter(path: str, key: str) -> int:
    ensure_dir(path)
    if os.path.exists(path):
        data = json.load(open(path, "r"))
    else:
        data = {}

    data[key] = data.get(key, 0) + 1

    json.dump(data, open(path, "w"), indent=2)
    return data[key]


def send_telegram(msg: str, preview=False):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_main = os.getenv("TELEGRAM_CHAT_ID_ENERGY")
    chat_test = os.getenv("TELEGRAM_CHAT_ID_TEST", "")
    thread = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "")

    if not token or not chat_main:
        print("Telegram não configurado.")
        return

    chat_id = chat_test if preview and chat_test else chat_main

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if thread:
        payload["message_thread_id"] = thread

    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        print("Mensagem enviada ao Telegram.")
    except Exception as e:
        print("Erro ao enviar Telegram:", e)
