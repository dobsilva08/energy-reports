#!/usr/bin/env python3
"""Central orchestrator for daily Energy Reports."""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = [
    ("Oil", "scripts/oil/oil_daily.py", ["--preview"]),
    ("Gas", "scripts/gas/gas_daily.py", ["--send-telegram", "--preview"]),
    ("ULSD", "scripts/gas/ulsd_daily_llm.py", ["--send-telegram", "--preview"]),
    ("Jet Fuel", "scripts/gas/jet_fuel_daily_llm.py", ["--send-telegram", "--preview"]),
    ("Uranium", "scripts/energy/uranium_daily_llm.py", ["--send-telegram", "--preview"]),
    ("Coal", "scripts/energy/coal_daily.py", ["--out", "pipelines/energy/coal_daily.json", "--preview"]),
    ("JKM LNG", "scripts/gas/jkm_lng_daily.py", ["--out", "pipelines/gas/jkm_lng_daily.json", "--preview"]),
    ("RBOB", "scripts/gas/rbob_daily.py", ["--out", "pipelines/gas/rbob_daily.json", "--preview"]),
]
# These scripts send directly to the production Telegram chat and do not honor
# preview/test routing. Skip them during preview rather than risk live delivery.
PREVIEW_SAFE = {"Oil", "Gas", "ULSD", "Jet Fuel", "Uranium"}

def run(name, script, args):
    print(f"\n=== {name} ===", flush=True)
    try:
        result = subprocess.run([sys.executable, script, *args], cwd=ROOT, env=os.environ.copy())
        if result.returncode:
            print(f"FAIL {name}: exit {result.returncode}", flush=True)
            return False
        print(f"OK {name}", flush=True)
        return True
    except Exception as exc:
        print(f"FAIL {name}: {exc}", flush=True)
        return False

def main():
    parser = argparse.ArgumentParser(description="Run daily energy reports")
    parser.add_argument("--preview", action="store_true", help="Preview/test routing where supported; skips direct production-send assets")
    args = parser.parse_args()
    failures = []
    skipped = []
    for name, script, preview_args in DAILY:
        if args.preview and name not in PREVIEW_SAFE:
            print(f"SKIP {name}: script lacks safe preview/test-chat routing", flush=True)
            skipped.append(name)
            continue
        cmd_args = preview_args if args.preview else [arg for arg in preview_args if arg != "--preview"]
        if not args.preview and name == "Oil":
            cmd_args = []
        failures.append(not run(name, script, cmd_args))
    print("\nSkipped in preview: " + (", ".join(skipped) if skipped else "none"), flush=True)
    print("\nDaily central run: " + ("FAILURES detected" if any(failures) else "all executed assets completed"), flush=True)
    sys.exit(1 if any(failures) else 0)

if __name__ == "__main__":
    main()
