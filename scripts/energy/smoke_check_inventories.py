#!/usr/bin/env python3
"""
Smoke test para os 3 CSVs de inventário:

Uso:
  python smoke_check_inventories.py \
    /tmp/petroleum_crude.csv \
    /tmp/petroleum_products.csv \
    /tmp/gas_storage.csv
"""

import sys
import pandas as pd


def check(path: str) -> None:
    print(f"[SMOKE] Checking {path}")
    df = pd.read_csv(path)
    if df is None or len(df) == 0:
        raise Exception(f"No data in {path}")

    if "date" in df.columns:
        # Converte para datetime; algumas datas podem vir com timezone
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        latest = df["date"].max()
        if pd.isna(latest):
            raise Exception(f"No valid date in {path}")

        # Normaliza: remove timezone se existir (vira tz-naive)
        if hasattr(latest, "tzinfo") and latest.tzinfo is not None:
            latest = latest.tz_convert(None)

        # cutoff também tz-naive (UTC agora - 45 dias)
        cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=45)

        if latest < cutoff:
            raise Exception(f"Latest date in {path} is too old: {latest} (cutoff {cutoff})")


if __name__ == "__main__":
    try:
        check(sys.argv[1])
        check(sys.argv[2])
        check(sys.argv[3])
        print("SMOKE OK")
        sys.exit(0)
    except Exception as e:
        print("SMOKE FAILED:", str(e))
        sys.exit(2)
