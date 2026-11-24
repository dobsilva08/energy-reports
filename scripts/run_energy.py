#!/usr/bin/env python3
"""Central Energy orchestrator. Preview is deliberately non-production-safe."""
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
]
DIRECT = [
    ("Coal", "scripts/energy/coal_daily.py", ["--out", "pipelines/energy/coal_daily.json", "--preview"]),
    ("JKM LNG", "scripts/gas/jkm_lng_daily.py", ["--out", "pipelines/gas/jkm_lng_daily.json", "--preview"]),
    ("RBOB", "scripts/gas/rbob_daily.py", ["--out", "pipelines/gas/rbob_daily.json", "--preview"]),
]

def run(name, script, args):
    print(f"\n=== {name} ===", flush=True)
    try:
        r = subprocess.run([sys.executable, script, *args], cwd=ROOT, env=os.environ.copy())
        if r.returncode:
            print(f"FAIL {name}: exit {r.returncode}", flush=True)
            return False
        print(f"OK {name}", flush=True)
        return True
    except Exception as e:
        print(f"FAIL {name}: {e}", flush=True)
        return False

def weekly(preview=False):
    if preview:
        print("Weekly EIA skipped in Preview: pipeline currently sends to production chat.")
        return True
    os.makedirs("/tmp/energy_dashboard", exist_ok=True)
    cmds = [
        ("EIA fetch", "scripts/energy/fetch_and_parse_eia.py", []),
        ("EIA validation", "scripts/energy/smoke_check_inventories.py", ["/tmp/petroleum_crude.csv", "/tmp/petroleum_products.csv", "/tmp/gas_storage.csv"]),
        ("Inventory messages", "scripts/energy/format_telegram_inventory.py", ["--crude", "/tmp/petroleum_crude.csv", "--products", "/tmp/petroleum_products.csv", "--gas", "/tmp/gas_storage.csv", "--out-crude", "/tmp/telegram_petroleum_crude.txt", "--out-products", "/tmp/telegram_petroleum_products.txt", "--out-gas", "/tmp/telegram_gas_storage.txt"]),
        ("Weekly summary", "scripts/energy/format_energy_weekly_summary.py", ["--crude", "/tmp/petroleum_crude.csv", "--products", "/tmp/petroleum_products.csv", "--gas", "/tmp/gas_storage.csv", "--out", "/tmp/telegram_energy_summary.txt"]),
        ("Charts", "scripts/energy/plot_energy_charts.py", ["--crude", "/tmp/petroleum_crude.csv", "--products", "/tmp/petroleum_products.csv", "--gas", "/tmp/gas_storage.csv", "--out-crude", "/tmp/crude_12w.png", "--out-products", "/tmp/products_12w.png", "--out-gas", "/tmp/gas_12w.png", "--out-gas-5y", "/tmp/gas_vs_5y.png", "--out-crude-seasonal", "/tmp/crude_seasonality_5y.png"]),
        ("Dashboard", "scripts/energy/build_energy_dashboard_html.py", ["--crude", "/tmp/petroleum_crude.csv", "--products", "/tmp/petroleum_products.csv", "--gas", "/tmp/gas_storage.csv", "--summary", "/tmp/telegram_energy_summary.txt", "--out", "/tmp/energy_dashboard/energy_weekly_dashboard.html"]),
    ]
    for n, s, a in cmds:
        if not run(n, s, a):
            return False
    import shutil
    for f in ["crude_12w.png", "products_12w.png", "gas_12w.png", "gas_vs_5y.png", "crude_seasonality_5y.png"]:
        if os.path.exists("/tmp/" + f):
            shutil.copy("/tmp/" + f, "/tmp/energy_dashboard/" + f)
    return True

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--preview", action="store_true")
    p.add_argument("--weekly-only", action="store_true")
    a = p.parse_args()
    if a.weekly_only:
        sys.exit(0 if weekly(a.preview) else 1)
    failed = []
    for n, s, base_args in DAILY:
        args = base_args if a.preview else [x for x in base_args if x != "--preview"]
        if n == "Oil" and not a.preview:
            args = []
        if n != "Oil" and not a.preview:
            args = [x for x in base_args if x != "--preview"]
        failed.append(not run(n, s, args))
    if a.preview:
        print("Preview: skipping Coal, JKM LNG and RBOB; their current implementations are not guaranteed to honor preview.")
    else:
        for n, s, base_args in DIRECT:
            args = [x for x in base_args if x != "--preview"]
            failed.append(not run(n, s, args))
    print("\nCentral run: " + ("FAILURES detected" if any(failed) else "all scheduled assets completed"), flush=True)
    sys.exit(1 if any(failed) else 0)

if __name__ == "__main__":
    main()
