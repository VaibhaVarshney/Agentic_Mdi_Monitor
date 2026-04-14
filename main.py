"""
main.py — Full pipeline orchestrator
Runs all agents in sequence: Watch → Warn → Match
Run this to regenerate everything from scratch.
Usage: python main.py
"""

import pandas as pd
import os
import sys

print("=" * 60)
print("MDI LIQUIDITY MONITOR — Full Pipeline")
print("=" * 60)

# ── Check data exists ─────────────────────────────────────────────────────────
if not os.path.exists("data/raw/mdi_financials.csv"):
    print("ERROR: Raw data not found.")
    print("Run these first:")
    print("  python get_mdi_list.py")
    print("  python get_financials.py")
    sys.exit(1)

# ── Step 1: Watch agent — compute ratios ──────────────────────────────────────
print("\n[1/3] Watch agent — computing liquidity ratios...")
from agents.watch import run_watch_agent
ratios = run_watch_agent()
print(f"      Done. {len(ratios)} rows processed.")

# ── Step 2: Warn agent — score risk ──────────────────────────────────────────
print("\n[2/3] Warn agent — scoring risk levels...")
from agents.warn import run_warn_agent
alerts = run_warn_agent(ratios)
print(f"      Done. {len(alerts)} banks flagged.")

# ── Step 3: Match agent — find programs and generate briefs ──────────────────
if len(alerts) > 0:
    print("\n[3/3] Match agent — matching federal programs...")
    from agents.match import run_match_agent
    mdis = pd.read_csv("data/raw/mdi_list.csv")
    for _, alert_row in alerts.head(3).iterrows():
        inst_rows = mdis[mdis['CERT'] == alert_row['CERT']]
        if len(inst_rows) > 0:
            inst_row = inst_rows.iloc[0]
            print(f"      Matching programs for {inst_row['INSTNAME']}...")
            results = run_match_agent(alert_row, inst_row)
            print(f"      Found {len(results)} eligible programs.")
else:
    print("\n[3/3] Match agent — no banks flagged, skipping.")

print("\n" + "=" * 60)
print("Pipeline complete.")
print(f"  Flagged banks: {len(alerts)}")
print(f"  Dashboard: streamlit run dashboard/app.py")
print("=" * 60)
