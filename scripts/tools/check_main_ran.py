#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/tools/check_main_ran.py

Verifica se o workflow principal (oil_daily) já enviou o relatório hoje (BRT).
Lógica:
 - 1) Checa sentinel persistente em data/sentinels/oil_daily.sent via GitHub Contents API.
 - 2) Se sentinel ausente ou desatualizado, procura por workflow runs do workflow principal
      (procura pelo arquivo oil_daily.yml ou pelo nome que contenha 'oil' e 'daily').
 - 3) Se nada encontrado, faz polling por um período (max_wait) rechecando sentinel + runs.
 - 4) Se encontrar um envio bem-sucedido (success) ou sentinel com data de hoje -> exit 0.
 - 5) Se timeout expirar sem encontrar nada -> exit 1 (watchdog deve executar).

Use no workflow:
- Configurar env GITHUB_TOKEN e GITHUB_REPOSITORY (o runner fornece automaticamente).

Retorna:
 - exit 0 -> main já enviou hoje (watchdog NÃO deve executar)
 - exit 1 -> main NÃO enviou hoje (watchdog deve executar)
"""

import os
import sys
import time
import json
import base64
import requests
from datetime import datetime, timezone, timedelta

# -------- CONFIG --------
# Tempo máximo de espera (seconds) e intervalo entre rechecagens (seconds)
DEFAULT_MAX_WAIT = int(os.getenv("CHECK_MAIN_MAX_WAIT", "90"))   # ajustar se quiser mais segurança
DEFAULT_INTERVAL = int(os.getenv("CHECK_MAIN_INTERVAL", "10"))

# Caminho do sentinel no repo
SENTINEL_PATH = os.getenv("SENTINEL_PATH", "data/sentinels/oil_daily.sent")
# Nomes candidatos do workflow file
WORKFLOW_FILENAMES = ["oil_daily.yml", "oil_daily.yaml"]

# BRT offset
BRT_OFFSET = timedelta(hours=-3)

# -------- Helpers --------
def log(*args, **kwargs):
    print(*args, **kwargs, flush=True)

def get_env_var(name):
    v = os.environ.get(name)
    if not v:
        log(f"[WARN] env {name} not set")
    return v

def iso_to_date(date_str):
    """Parse ISO YYYY-MM-DD or full ISO datetime."""
    try:
        # try YYYY-MM-DD
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        try:
            # try full ISO with timezone Z
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.date()
        except Exception:
            return None

# -------- Core checks --------
def check_sentinel(repo, headers):
    """
    Return True if sentinel exists and has last_sent == today (BRT).
    """
    url = f"https://api.github.com/repos/{repo}/contents/{SENTINEL_PATH}"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            payload = r.json()
            content_b64 = payload.get("content", "")
            if not content_b64:
                log("[DEBUG] sentinel content empty")
                return False
            raw = base64.b64decode(content_b64).decode()
            try:
                data = json.loads(raw)
            except Exception:
                # try to be lenient: if file is plain like {"last_sent":"YYYY-MM-DD"}
                try:
                    data = json.loads(raw.strip())
                except Exception as e:
                    log("[WARN] failed to parse sentinel JSON:", e)
                    return False
            last_sent = data.get("last_sent")
            if not last_sent:
                return False
            today_brt = (datetime.now(timezone.utc) + BRT_OFFSET).date()
            sent_date = iso_to_date(last_sent)
            if sent_date and sent_date == today_brt:
                log(f"[INFO] Sentinel found with today's date: {last_sent}")
                return True
            else:
                log(f"[DEBUG] Sentinel present but not today: {last_sent}")
                return False
        else:
            log(f"[DEBUG] Sentinel request returned {r.status_code} (likely not found)")
            return False
    except Exception as e:
        log("[WARN] exception while checking sentinel:", e)
        return False

def find_workflow_id(repo, headers):
    """
    Return workflow id for oil_daily workflow, or None if not found.
    Strategy:
      1) list workflows and match path ending with candidate filenames
      2) fallback: match workflow name containing 'oil' and 'daily'
    """
    try:
        url = f"https://api.github.com/repos/{repo}/actions/workflows"
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            log(f"[WARN] list workflows failed: {r.status_code}")
            return None
        workflows = r.json().get("workflows", [])
        # first try filename match
        for w in workflows:
            path = (w.get("path") or "").lower()
            for fn in WORKFLOW_FILENAMES:
                if path.endswith(fn):
                    log(f"[DEBUG] workflow file matched: {path} -> id {w.get('id')}")
                    return w.get("id")
        # fallback: match by name
        for w in workflows:
            name = (w.get("name") or "").lower()
            if "oil" in name and "daily" in name:
                log(f"[DEBUG] workflow name matched: {name} -> id {w.get('id')}")
                return w.get("id")
        # last resort: try any workflow with 'oil' in name
        for w in workflows:
            name = (w.get("name") or "").lower()
            if "oil" in name:
                log(f"[DEBUG] workflow loose match: {name} -> id {w.get('id')}")
                return w.get("id")
        return None
    except Exception as e:
        log("[WARN] exception while finding workflow id:", e)
        return None

def check_workflow_runs_for_today(repo, headers, wf_id):
    """
    Look at recent workflow runs for the workflow id and return True if any run
    has conclusion == 'success' and created_at falls on today's BRT date.
    """
    try:
        per_page = 100
        pages = 2  # check up to N pages (200 runs)
        today_brt = (datetime.now(timezone.utc) + BRT_OFFSET).date()
        for page in range(1, pages + 1):
            url = f"https://api.github.com/repos/{repo}/actions/workflows/{wf_id}/runs?per_page={per_page}&page={page}"
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                log(f"[DEBUG] runs request page {page} returned {r.status_code}")
                continue
            runs = r.json().get("workflow_runs", [])
            if not runs:
                break
            for run in runs:
                if run.get("conclusion") != "success":
                    continue
                created_at = run.get("created_at")
                if not created_at:
                    continue
                # created_at is ISO UTC string like '2025-11-14T09:12:34Z'
                try:
                    dt_utc = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    log("[DEBUG] failed to parse created_at:", created_at)
                    continue
                dt_brt = dt_utc + BRT_OFFSET
                if dt_brt.date() == today_brt:
                    log(f"[INFO] Found successful workflow run today: run_id={run.get('id')} created_at(BRT)={dt_brt}")
                    return True
        return False
    except Exception as e:
        log("[WARN] exception while checking workflow runs:", e)
        return False

# -------- Main logic --------
def main():
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")

    if not repo or not token:
        log("[ERROR] GITHUB_REPOSITORY or GITHUB_TOKEN not set in env. Abort.")
        sys.exit(0)  # fail safe: if token not present we choose NOT to run watchdog (avoid accidental duplicate sends)

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    max_wait = DEFAULT_MAX_WAIT
    interval = DEFAULT_INTERVAL
    try:
        max_wait = int(os.getenv("CHECK_MAIN_MAX_WAIT", str(DEFAULT_MAX_WAIT)))
        interval = int(os.getenv("CHECK_MAIN_INTERVAL", str(DEFAULT_INTERVAL)))
    except Exception:
        pass

    log(f"[INFO] check_main_ran starting. repo={repo} max_wait={max_wait}s interval={interval}s sentinel_path={SENTINEL_PATH}")

    # immediate check
    try:
        if check_sentinel(repo, headers):
            log("[RESULT] sentinel indicates already sent today -> exit 0")
            sys.exit(0)
    except Exception as e:
        log("[WARN] sentinel check raised:", e)

    wf_id = find_workflow_id(repo, headers)
    if wf_id:
        try:
            if check_workflow_runs_for_today(repo, headers, wf_id):
                log("[RESULT] workflow run success found for today -> exit 0")
                sys.exit(0)
        except Exception as e:
            log("[WARN] workflow runs check raised:", e)

    # Polling loop
    start = time.time()
    while time.time() - start < max_wait:
        log("[DEBUG] waiting and rechecking...")
        time.sleep(interval)
        try:
            if check_sentinel(repo, headers):
                log("[RESULT] sentinel found after wait -> exit 0")
                sys.exit(0)
        except Exception as e:
            log("[WARN] sentinel recheck raised:", e)

        if wf_id:
            try:
                if check_workflow_runs_for_today(repo, headers, wf_id):
                    log("[RESULT] workflow run found after wait -> exit 0")
                    sys.exit(0)
            except Exception as e:
                log("[WARN] workflow runs recheck raised:", e)
        else:
            # try to find workflow id on subsequent iterations in case it appears now
            wf_id = find_workflow_id(repo, headers)
            if wf_id:
                log(f"[DEBUG] found workflow id during polling: {wf_id}")

    # nothing found within timeout -> instruct watchdog to run
    log("[RESULT] NO successful run or sentinel found within timeout -> exit 1 (watchdog should execute)")
    sys.exit(1)


if __name__ == "__main__":
    main()
