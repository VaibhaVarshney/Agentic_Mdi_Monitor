import requests
import pandas as pd
import numpy as np
import os
from config import WEIGHTS

os.makedirs("data/backtest", exist_ok=True)

print("=" * 50)
print("STEP 4: Back-test — Ponce Bank (Bronx, NY)")
print("=" * 50)

# Using Ponce Bank (CERT: 31189) — real MDI, currently flagged critical
# This shows our system tracking a real bank under stress RIGHT NOW
BACKTEST_CERT = 31189
BACKTEST_NAME = "Ponce Bank, National Association"

FIELDS = [
    "CERT", "REPDTE",
    "DEP", "LNLSNET", "CHBAL", "RBC1AAJ",
    "ASSET", "COREDEP", "NETINC", "EQ"
]

print(f"Pulling {BACKTEST_NAME} history (CERT: {BACKTEST_CERT})...")

params = {
    "filters": f"CERT:{BACKTEST_CERT}",
    "fields": ",".join(FIELDS),
    "limit": 40,
    "sort_by": "REPDTE",
    "sort_order": "DESC",
    "output": "json"
}

r = requests.get("https://banks.data.fdic.gov/api/financials",
                 params=params, timeout=60)
api_data = r.json().get('data', [])

if not api_data:
    print("ERROR: No data returned for Ponce Bank")
    exit()

df = pd.DataFrame([d['data'] for d in api_data])
df = df.sort_values('REPDTE').reset_index(drop=True)
print(f"Got {len(df)} quarters")
print(f"Date range: {df['REPDTE'].min()} to {df['REPDTE'].max()}")

# Convert to numeric
for col in df.columns:
    if col not in ['CERT', 'REPDTE', 'ID']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

# Compute ratios using correct FDIC BankFind field names
df['deposits'] = df['DEP']
df['loans'] = df['LNLSNET']
df['cash'] = df['CHBAL']
df['assets'] = df['ASSET']
df['core_dep'] = df['COREDEP']

df['T1R'] = df['RBC1AAJ'] / 100.0   # already a percentage
df['LTD'] = df['loans'] / df['deposits']
df['CBD'] = (df['cash'] / (df['deposits'] / 365)).clip(upper=300)
df['BDR'] = ((df['deposits'] - df['core_dep']) / df['deposits']).clip(lower=0)

df = df.dropna(subset=['LTD', 'T1R', 'CBD', 'BDR'])
df = df.sort_values('REPDTE').reset_index(drop=True)

# Rolling 4-quarter baseline
for col in ['LTD', 'T1R', 'CBD', 'BDR']:
    df[f'{col}_baseline'] = df[col].shift(1).rolling(4, min_periods=2).mean()
    df[f'{col}_delta'] = df[col] - df[f'{col}_baseline']

# Risk score


def normalize(val, lo, hi, invert=False):
    try:
        n = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
        return 1.0 - n if invert else n
    except:
        return 0.0


def risk(row):
    try:
        base = (
            WEIGHTS['ltd'] * normalize(row['LTD'], 0.70, 1.10) +
            WEIGHTS['t1'] * normalize(row['T1R'], 0.20, 0.06, invert=True) +
            WEIGHTS['cbd'] * normalize(row['CBD'], 120,  8,    invert=True) +
            WEIGHTS['bdr'] * normalize(row['BDR'], 0.05, 0.40)
        ) * 100
        deteriorating = sum([
            row.get('LTD_delta', 0) > 0.04,
            row.get('T1R_delta', 0) < -0.008,
            row.get('CBD_delta', 0) < -4,
        ])
        return round(min(100.0, base * (1 + deteriorating * 0.12)), 1)
    except:
        return 0.0


def sev(s):
    if s < 30:
        return "low"
    if s < 55:
        return "medium"
    if s < 75:
        return "high"
    return "critical"


df['RISK_SCORE'] = df.apply(risk, axis=1)
df['SEVERITY'] = df['RISK_SCORE'].apply(sev)
df['INSTNAME'] = BACKTEST_NAME

df.to_csv("data/backtest/highland_scored.csv", index=False)

# Print last 20 quarters
print(f"\n{BACKTEST_NAME} — Risk Score History")
print(f"{'Quarter':<12} {'LTD':>6} {'T1R':>6} {'CBD':>7} {'Score':>6} {'Severity'}")
print("-" * 60)
for _, row in df.tail(20).iterrows():
    marker = " ← ALERT" if row['SEVERITY'] in ['high', 'critical'] else ""
    print(f"{str(row['REPDTE']):<12} {row['LTD']:>6.3f} "
          f"{row['T1R']:>6.3f} {row['CBD']:>7.1f} "
          f"{row['RISK_SCORE']:>6.1f} {row['SEVERITY']}{marker}")

# Show trend — when did risk start rising?
recent = df.tail(12)
first_flagged = recent[recent['SEVERITY'].isin(['high', 'critical'])]

print(f"\nRisk score trend (last 12 quarters):")
for _, row in recent.iterrows():
    bar = "█" * int(row['RISK_SCORE'] / 5)
    print(
        f"  {str(row['REPDTE']):<12} {bar:<20} {row['RISK_SCORE']:>5.1f} {row['SEVERITY']}")

if len(first_flagged) > 0:
    print(f"\nFirst HIGH/CRITICAL alert: {first_flagged['REPDTE'].min()}")
    print(f"Current status: {df.iloc[-1]['SEVERITY'].upper()} "
          f"(score {df.iloc[-1]['RISK_SCORE']})")
    print(f"\nThis bank is CURRENTLY at risk.")
    print(
        f"Our system would have flagged it {len(first_flagged)} quarters ago.")
    print(
        f"That's approximately {len(first_flagged) * 90} days of advance warning.")

print(f"\nSaved: data/backtest/highland_scored.csv")
print("Run next: python verify_data.py")
