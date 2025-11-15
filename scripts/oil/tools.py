# scripts/oil/tools.py
import os
import json
from datetime import datetime, timezone, timedelta

BRT_OFFSET = timedelta(hours=-3)

def ensure_dir_for_file(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

def title_counter(counter_path: str, key: str = 'diario_oil') -> int:
    ensure_dir_for_file(counter_path)
    try:
        data = json.load(open(counter_path, 'r', encoding='utf-8')) if os.path.exists(counter_path) else {}
    except Exception:
        data = {}
    data[key] = int(data.get(key, 0)) + 1
    json.dump(data, open(counter_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    return data[key]

def sent_guard(path: str) -> bool:
    """
    If the sentinel file already indicates today (BRT), return True (already sent).
    Otherwise update it and return False.
    """
    ensure_dir_for_file(path)
    today_tag = (datetime.now(timezone.utc) + BRT_OFFSET).strftime('%Y-%m-%d')
    if os.path.exists(path):
        try:
            data = json.load(open(path, 'r', encoding='utf-8'))
            if data.get('last_sent') == today_tag:
                return True
        except Exception:
            pass
    json.dump({'last_sent': today_tag}, open(path, 'w', encoding='utf-8'))
    return False

def send_to_telegram(text: str, preview: bool = False) -> None:
    """
    Sends message to TELEGRAM_CHAT_ID_ENERGY unless preview and TELEGRAM_CHAT_ID_TEST exists.
    """
    try:
        import requests
    except Exception:
        print("requests not available; skipping telegram send.")
        return

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_main = os.environ.get('TELEGRAM_CHAT_ID_ENERGY', '').strip()
    chat_test = os.environ.get('TELEGRAM_CHAT_ID_TEST', '').strip()
    chat = chat_test if (preview and chat_test) else chat_main
    if not bot_token or not chat:
        print("Telegram not configured (missing token or chat). Skipping send.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        print("Telegram: mensagem enviada.")
    except Exception as e:
        print("Falha no envio ao Telegram:", e)
