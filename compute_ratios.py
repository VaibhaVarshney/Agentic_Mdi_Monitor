import pandas as pd
import numpy as np
import os
from config import THRESHOLDS, WEIGHTS

os.makedirs("data/processed", exist_ok=True)

print("=" * 50)
print("STEP 3: Computing liquidity ratios and risk scores")
print("=" * 50)

fin = pd.read_csv("data/raw/mdi_financials.csv")
mdis = pd.read_csv("data/raw/mdi_list.csv")
print(f"Loaded {len(fin)} rows for {fin['CERT'].nunique()} banks")

# Convert all numeric columns
for col in ['DEP', 'LNLSNET', 'CHBAL', 'RBC1AAJ', 'ASSET', 'COREDEP',
            'NETINC', 'LNLSDEPR', 'LNLSNTV', 'EQ', 'RBCRWAJ']:
    if col in fin.columns:
        fin[col] = pd.to_numeric(fin[col], errors='coerce')

# ── Assign clean names ───────────────────────────────────────────
fin['deposits'] = fin['DEP']        # total deposits ($000)
fin['loans'] = fin['LNLSNET']    # net loans ($000)
fin['cash'] = fin['CHBAL']      # cash and balances ($000)
fin['assets'] = fin['ASSET']      # total assets ($000)
fin['equity'] = fin['EQ']         # total equity ($000)
fin['net_income'] = fin['NETINC']     # net income ($000)
fin['core_dep'] = fin['COREDEP']    # core deposits ($000)

# RBC1AAJ is already Tier 1 capital ratio as a PERCENTAGE
# e.g. 14.15 means 14.15% — divide by 100 for decimal
fin['T1R'] = fin['RBC1AAJ'] / 100.0

# ── Compute the other 3 ratios ───────────────────────────────────
# LTD: loan-to-deposit ratio (above 0.95 = critical)
fin['LTD'] = fin['loans'] / fin['deposits']

# CBD: cash buffer days (below 15 = warning)
fin['CBD'] = fin['cash'] / (fin['deposits'] / 365)

# BDR: non-core funding ratio — proxy for brokered deposit risk
# (deposits minus core deposits) / total deposits
fin['BDR'] = (fin['deposits'] - fin['core_dep']) / fin['deposits']
fin['BDR'] = fin['BDR'].clip(lower=0)  # can't be negative

# Drop rows where core ratios can't be computed
fin = fin.dropna(subset=['LTD', 'T1R', 'CBD', 'BDR'])
fin = fin[fin['assets'] >= 50000]
# Cap CBD at 300 days for scoring purposes
fin['CBD'] = fin['CBD'].clip(upper=300)

fin = fin.sort_values(['CERT', 'REPDTE'])
print(f"Rows after cleaning: {len(fin)}")

# ── Sanity check ─────────────────────────────────────────────────
print(f"\nRatio sanity check (should be reasonable ranges):")
print(
    f"  LTD range: {fin['LTD'].min():.3f} – {fin['LTD'].max():.3f}  (expect 0.2 – 1.5)")
print(
    f"  T1R range: {fin['T1R'].min():.3f} – {fin['T1R'].max():.3f}  (expect 0.05 – 0.50)")
print(
    f"  CBD range: {fin['CBD'].min():.1f} – {fin['CBD'].max():.1f}  (expect 5 – 300 days)")
print(
    f"  BDR range: {fin['BDR'].min():.3f} – {fin['BDR'].max():.3f}  (expect 0 – 0.5)")

# ── Rolling 4-quarter baseline per bank ──────────────────────────
for col in ['LTD', 'T1R', 'CBD', 'BDR']:
    fin[f'{col}_baseline'] = (
        fin.groupby('CERT')[col]
        .transform(lambda x: x.shift(1).rolling(4, min_periods=2).mean())
    )
    fin[f'{col}_delta'] = fin[col] - fin[f'{col}_baseline']

# ── Composite risk score ──────────────────────────────────────────


def normalize(val, lo, hi, invert=False):
    try:
        n = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
        return 1.0 - n if invert else n
    except:
        return 0.0


def compute_risk_score(row):
    try:
        # Cap CBD at 300 days to prevent outliers distorting the score
        cbd_capped = min(float(row['CBD']), 300)

        base = (
            WEIGHTS['ltd'] * normalize(row['LTD'], 0.70, 1.10) +
            WEIGHTS['t1'] * normalize(row['T1R'], 0.20, 0.06, invert=True) +
            WEIGHTS['cbd'] * normalize(cbd_capped,  120,  8,   invert=True) +
            WEIGHTS['bdr'] * normalize(row['BDR'], 0.05, 0.40)
        ) * 100

        bad_trends = sum([
            row.get('LTD_delta', 0) > 0.05,
            row.get('T1R_delta', 0) < -0.01,
            row.get('CBD_delta', 0) < -5,
        ])
        return round(min(100.0, base * (1 + bad_trends * 0.08)), 1)
    except:
        return 0.0


def assign_severity(score):
    if score < 30:
        return "low"
    if score < 55:
        return "medium"
    if score < 75:
        return "high"
    return "critical"


fin['RISK_SCORE'] = fin.apply(compute_risk_score, axis=1)
fin['SEVERITY'] = fin['RISK_SCORE'].apply(assign_severity)

# ── Merge bank names ──────────────────────────────────────────────
fin = fin.merge(
    mdis[['CERT', 'INSTNAME', 'CITY', 'STALP']],
    on='CERT', how='left'
)

# ── Save outputs ──────────────────────────────────────────────────
fin.to_csv("data/processed/mdi_ratios.csv", index=False)

latest = fin.sort_values('REPDTE').groupby('CERT').tail(1).copy()
latest.to_csv("data/processed/mdi_latest.csv", index=False)

alerts = latest[latest['SEVERITY'].isin(['high', 'critical'])].copy()
alerts = alerts.sort_values('RISK_SCORE', ascending=False)
alerts.to_csv("data/processed/mdi_alerts.csv", index=False)

# ── Summary ───────────────────────────────────────────────────────
print(f"\nSeverity breakdown (latest quarter):")
print(latest['SEVERITY'].value_counts().to_string())

print(f"\nFlagged banks — high/critical ({len(alerts)} total):")
if len(alerts) > 0:
    print(alerts[['INSTNAME', 'CITY', 'STALP',
                  'RISK_SCORE', 'SEVERITY', 'LTD', 'T1R', 'CBD'
                  ]].round(3).to_string(index=False))
else:
    print("None flagged.")

print(f"\nFiles saved:")
print(f"  data/processed/mdi_ratios.csv  — {len(fin)} rows")
print(f"  data/processed/mdi_latest.csv  — {len(latest)} rows")
print(f"  data/processed/mdi_alerts.csv  — {len(alerts)} flagged banks")
print("\nRun next: python get_highland.py")
