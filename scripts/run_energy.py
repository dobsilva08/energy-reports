#!/usr/bin/env python3
"""Central daily Energy Reports runner with validation and failure aggregation."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = [
    ("Oil", "scripts/oil/oil_daily.py", []),
    ("Natural Gas", "scripts/gas/gas_daily.py", ["--send-telegram"]),
    ("ULSD", "scripts/gas/ulsd_daily_llm.py", ["--send-telegram"]),
    ("Jet Fuel", "scripts/gas/jet_fuel_daily_llm.py", ["--send-telegram"]),
    ("Uranium", "scripts/energy/uranium_daily_llm.py", ["--send-telegram"]),
    ("Coal", "scripts/energy/coal_daily.py", ["--out", "pipelines/energy/coal_daily.json"]),
    ("JKM LNG", "scripts/gas/jkm_lng_daily.py", ["--out", "pipelines/gas/jkm_lng_daily.json"]),
    ("RBOB", "scripts/gas/rbob_daily.py", ["--out", "pipelines/gas/rbob_daily.json"]),
]

def validate():
    print("Static validation: compiling all Python files.", flush=True)
    result = subprocess.run([sys.executable, "-m", "compileall", "-q", "providers", "scripts"], cwd=ROOT)
    if result.returncode:
        return result.returncode
    missing = [script for _, script, _ in ASSETS if not (ROOT / script).is_file()]
    if missing:
        print("Missing daily scripts: " + ", ".join(missing), flush=True)
        return 1
    print("Static validation passed. Preview mode does not call external APIs or Telegram.", flush=True)
    return 0

def run_asset(name, script, args):
    print(f"\n===== {name} =====", flush=True)
    try:
        return subprocess.run([sys.executable, script, *args], cwd=ROOT, env=os.environ.copy(), timeout=600).returncode == 0
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {name} exceeded 10 minutes", flush=True)
        return False
    except Exception as exc:
        print(f"ERROR running {name}: {exc}", flush=True)
        return False

def notify_failure(failed):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID_ENERGY", "").strip()
    if not token or not chat:
        print("Cannot send failure summary: Telegram credentials missing.", flush=True)
        return
    import requests
    msg = "⚠️ <b>Energy Reports — execução com falhas</b>\n\n" + "\n".join("• " + x for x in failed)
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": msg, "parse_mode": "HTML"}, timeout=30)
        r.raise_for_status()
        if not r.json().get("ok"):
            raise RuntimeError(r.text)
    except Exception as exc:
        print(f"Failure-summary Telegram notification failed: {exc}", flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Compile and validate only; no API calls or Telegram sends")
    args = parser.parse_args()
    if args.preview:
        sys.exit(validate())
    failed = []
    for name, script, cmd_args in ASSETS:
        if not run_asset(name, script, cmd_args):
            failed.append(name)
    if failed:
        print("\nFAILED assets: " + ", ".join(failed), flush=True)
        notify_failure(failed)
        sys.exit(1)
    print("\nAll daily assets completed successfully.", flush=True)

if __name__ == "__main__":
    main()
