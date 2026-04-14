"""
agents/warn.py — Warn Agent
OWNED BY: P3
Takes ratio data from Watch agent, assigns risk scores,
generates severity labels, and creates alert records.
"""

import pandas as pd
import os
from config import WEIGHTS, THRESHOLDS

os.makedirs("data/processed", exist_ok=True)


def normalize(val, lo, hi, invert=False):
    try:
        n = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
        return 1.0 - n if invert else n
    except:
        return 0.0


def compute_risk_score(row):
    """Composite risk score 0-100. Above 55 = high. Above 75 = critical."""
    try:
        base = (
            WEIGHTS['ltd'] * normalize(row['LTD'], 0.70, 1.05) +
            WEIGHTS['t1']  * normalize(row['T1R'], 0.12, 0.055, invert=True) +
            WEIGHTS['cbd'] * normalize(row['CBD'], 45,   8,     invert=True) +
            WEIGHTS['bdr'] * normalize(row['BDR'], 0.05, 0.25)
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
    if score < 30:  return "low"
    if score < 55:  return "medium"
    if score < 75:  return "high"
    return "critical"


def run_warn_agent(ratios_df):
    """Score all banks and return flagged alerts."""
    ratios_df = ratios_df.copy()
    ratios_df['RISK_SCORE'] = ratios_df.apply(compute_risk_score, axis=1)
    ratios_df['SEVERITY']   = ratios_df['RISK_SCORE'].apply(assign_severity)

    latest = ratios_df.sort_values('REPDTE').groupby('CERT').tail(1)
    latest.to_csv("data/processed/mdi_latest.csv", index=False)

    alerts = latest[latest['SEVERITY'].isin(['high', 'critical'])].copy()
    alerts = alerts.sort_values('RISK_SCORE', ascending=False)
    alerts.to_csv("data/processed/mdi_alerts.csv", index=False)
    return alerts


# P3: Add your enhancements below this line
# Ideas: trend extrapolation, days-to-threshold, human review gate
