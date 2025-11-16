# scripts/gas/tools.py
import os
import json
from datetime import datetime, timezone, timedelta

try:
    import requests
except Exception:
    requests = None

BRT = timezone(timedelta(hours=-3))

def ensure_dir_for_file(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

def title_counter(counter_path: str, key: str = 'diario_gas') -> int:
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
    Return True if sentinel indicates already sent today (BRT).
    Otherwise update sentinel and return False.
    """
    ensure_dir_for_file(path)
    today_tag = (datetime.now(timezone.utc) + timedelta(hours=-3)).strftime('%Y-%m-%d')
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
    if not requests:
        print("requests not available; skipping Telegram send.")
        return
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_main = os.environ.get('TELEGRAM_CHAT_ID_ENERGY', '').strip()
    chat_test = os.environ.get('TELEGRAM_CHAT_ID_TEST', '').strip()
    thread_id = os.environ.get('TELEGRAM_MESSAGE_THREAD_ID', '').strip()
    chat = chat_test if (preview and chat_test) else chat_main
    if not bot_token or not chat:
        print("Telegram not configured. Skipping send.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if thread_id:
        payload["message_thread_id"] = thread_id
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        print("Telegram: mensagem enviada.")
    except Exception as e:
        print("Falha no envio ao Telegram:", e)
