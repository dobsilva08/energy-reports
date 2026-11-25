# scripts/gas/tools.py
import os
import json
import re
import html
import requests
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

def normalize_telegram_html(text: str) -> str:
    """Normalize common LLM HTML wrappers to Telegram-supported HTML."""
    text = re.sub(r"(?is)<!doctype[^>]*>", "", text)
    # Telegram HTML does not support <br>; convert it to real line breaks.
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    # LLMs sometimes wrap a report in full-document tags.
    text = re.sub(r"(?i)<\s*/?\s*(html|body)\s*>", "", text)
    # Keep only Telegram's supported formatting tags. Unsupported wrappers
    # are removed, but their text is preserved.
    allowed = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "blockquote", "tg-spoiler"}
    def clean_tag(match):
        tag = match.group(0)
        name = re.match(r"<\s*/?\s*([a-zA-Z0-9-]+)", tag)
        if not name:
            return tag
        tag_name = name.group(1).lower()
        return tag if tag_name in allowed else ""
    text = re.sub(r"<[^>]+>", clean_tag, text)
    return text.strip()


def send_to_telegram(text: str, preview: bool = False) -> None:
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_main = os.environ.get('TELEGRAM_CHAT_ID_ENERGY', '').strip()
    chat_test = os.environ.get('TELEGRAM_CHAT_ID_TEST', '').strip()
    thread_id = os.environ.get('TELEGRAM_MESSAGE_THREAD_ID', '').strip()
    chat = chat_test if (preview and chat_test) else chat_main
    if not bot_token or not chat:
        raise RuntimeError("Telegram credentials not configured.")

    # Normalize LLM-generated wrappers/tags before Telegram HTML delivery.
    text = normalize_telegram_html(text)
    if len(text) > 4000:
        raise RuntimeError(f"Telegram HTML report too long ({len(text)} chars); chunking required.")
    payload={"chat_id":chat,"text":text,"parse_mode":"HTML","disable_web_page_preview":True}
    if thread_id: payload["message_thread_id"]=thread_id
    response=requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",json=payload,timeout=30)
    data=response.json()
    migrated_id=data.get("parameters", {}).get("migrate_to_chat_id") if isinstance(data,dict) else None
    if migrated_id:
        payload["chat_id"]=migrated_id
        response=requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",json=payload,timeout=30)
        data=response.json()
    if response.status_code >= 400 or not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    print("Telegram sent (HTML formatting preserved and normalized).")
