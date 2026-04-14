import pandas as pd
import os

print("=" * 50)
print("STEP 5: Data quality verification")
print("=" * 50)

issues = []
passed = []

# ── Check file existence ──────────────────────────────────────────────────────
required_files = [
    "data/raw/mdi_list.csv",
    "data/raw/mdi_financials.csv",
    "data/processed/mdi_ratios.csv",
    "data/processed/mdi_latest.csv",
    "data/processed/mdi_alerts.csv",
    "data/backtest/highland_scored.csv",
]

print("\nChecking files exist...")
for f in required_files:
    if os.path.exists(f):
        size = os.path.getsize(f) / 1024
        print(f"  OK  {f} ({size:.0f} KB)")
        passed.append(f)
    else:
        print(f"  MISSING  {f}")
        issues.append(f"Missing file: {f}")

# ── Check MDI list ────────────────────────────────────────────────────────────
if "data/raw/mdi_list.csv" in passed:
    print("\nChecking MDI list...")
    mdis = pd.read_csv("data/raw/mdi_list.csv")
    n = len(mdis)
    if n < 50:
        issues.append(f"Only {n} MDIs found — expected ~144")
    else:
        print(f"  OK  {n} MDIs found (expected ~144)")
    states = mdis['STALP'].nunique()
    print(f"  OK  {states} states covered")

# ── Check financials ──────────────────────────────────────────────────────────
if "data/raw/mdi_financials.csv" in passed:
    print("\nChecking financial data...")
    fin = pd.read_csv("data/raw/mdi_financials.csv")
    print(f"  OK  {len(fin)} rows, {fin['CERT'].nunique()} banks")
    print(f"  OK  Date range: {fin['REPDTE'].min()} → {fin['REPDTE'].max()}")
    missing_dep = fin['DEP'].isnull().sum()
    missing_t1 = fin['RBC1AAJ'].isnull().sum()
    if missing_dep > 50:
        issues.append(
            f"{missing_dep} rows missing DEP (deposits) — too many nulls")
    else:
        print(f"  OK  RCON2200 nulls: {missing_dep} (acceptable)")
    if missing_t1 > 50:
        issues.append(
            f"{missing_t1} rows missing RBC1AAJ (Tier 1) — too many nulls")
    else:
        print(f"  OK  RCON8274 nulls: {missing_t1} (acceptable)")

# ── Check ratios ──────────────────────────────────────────────────────────────
if "data/processed/mdi_ratios.csv" in passed:
    print("\nChecking computed ratios...")
    rat = pd.read_csv("data/processed/mdi_ratios.csv")
    print(f"  OK  {len(rat)} rows with valid ratios")
    ltd_max = rat['LTD'].max()
    t1r_min = rat['T1R'].min()
    cbd_min = rat['CBD'].min()
    if ltd_max > 5:
        issues.append(f"LTD max is {ltd_max:.2f} — likely a division error")
    else:
        print(f"  OK  LTD range: {rat['LTD'].min():.3f} – {ltd_max:.3f}")
    if t1r_min < 0:
        issues.append(f"Negative T1R found — check for null assets")
    else:
        print(f"  OK  T1R range: {t1r_min:.3f} – {rat['T1R'].max():.3f}")
    if cbd_min < 0:
        issues.append(f"Negative CBD found — check for null deposits")
    else:
        print(f"  OK  CBD range: {cbd_min:.1f} – {rat['CBD'].max():.1f} days")
    print(
        f"  OK  Risk score range: {rat['RISK_SCORE'].min()} – {rat['RISK_SCORE'].max()}")

# ── Check latest and alerts ───────────────────────────────────────────────────
if "data/processed/mdi_latest.csv" in passed:
    print("\nChecking latest snapshot...")
    lat = pd.read_csv("data/processed/mdi_latest.csv")
    print(f"  OK  {len(lat)} banks in latest snapshot")
    print(f"\n  Severity breakdown:")
    for sev, cnt in lat['SEVERITY'].value_counts().items():
        print(f"    {sev:<10} {cnt}")

if "data/processed/mdi_alerts.csv" in passed:
    alrt = pd.read_csv("data/processed/mdi_alerts.csv")
    if len(alrt) == 0:
        issues.append(
            "INFO: 0 banks flagged. Consider lowering thresholds in config.py.")
    else:
        print(f"\n  Flagged banks: {len(alrt)}")

# ── Check back-test ───────────────────────────────────────────────────────────
if "data/backtest/highland_scored.csv" in passed:
    print("\nChecking Highland back-test...")
    h = pd.read_csv("data/backtest/highland_scored.csv")
    # Convert REPDTE to int for comparison
    h['REPDTE'] = pd.to_numeric(h['REPDTE'], errors='coerce')
    print(f"  OK  {len(h)} quarters of Highland history")
    print(f"  OK  Date range: {h['REPDTE'].min()} → {h['REPDTE'].max()}")
    high_qtrs = h[h['SEVERITY'].isin(['high', 'critical'])]
    if len(high_qtrs) == 0:
        issues.append(
            "Back-test bank never reaches HIGH severity — weights need tuning")
    else:
        first = high_qtrs['REPDTE'].min()
        # Count quarters flagged before Jan 2023
        quarters_early = len(h[
            (h['REPDTE'] >= first) &
            (h['REPDTE'] < 20230101)
        ])
        print(f"  OK  First alert fires at: {first}")
        if quarters_early >= 2:
            print(f"  OK  {quarters_early} quarters ({quarters_early * 90} days) "
                  f"of early warning before 2023 — meets the claim!")
        else:
            print(f"  INFO  {quarters_early} quarters flagged before 2023 "
                  f"— consider using Ponce Bank story (ongoing risk) instead")
        # Show current status
        latest_row = h.iloc[-1]
        print(f"  OK  Current status: {latest_row['SEVERITY'].upper()} "
              f"(score {latest_row['RISK_SCORE']})")

# ── Final result ──────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
if issues:
    print("ISSUES TO FIX:")
    for i in issues:
        print(f"  - {i}")
    print("\nFix these before sharing with teammates.")
else:
    print("ALL CHECKS PASSED")
    print("\nUpload these files to Google Drive and share with your team:")
    for f in required_files:
        print(f"  {f}")
