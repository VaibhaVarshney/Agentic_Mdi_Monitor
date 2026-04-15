"""
agents/watch.py — Watch Agent
OWNED BY: P2
Reads raw FDIC financial data, computes liquidity ratios,
builds rolling baselines, and outputs scored data.
"""

import pandas as pd
import numpy as np
import os
from scipy import stats
from config import WEIGHTS

os.makedirs("data/processed", exist_ok=True)


def normalize(val, lo, hi, invert=False):
    try:
        n = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
        return 1.0 - n if invert else n
    except:
        return 0.0


def compute_ratios(df):
    """Compute the 4 core liquidity ratios from FDIC BankFind field names."""
    d = df.copy()

    numeric_cols = [
        'DEP', 'LNLSNET', 'CHBAL', 'RBC1AAJ',
        'ASSET', 'COREDEP', 'NETINC', 'EQ'
    ]
    for col in numeric_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors='coerce')

    d['deposits'] = d['DEP']
    d['loans'] = d['LNLSNET']
    d['cash'] = d['CHBAL']
    d['tier1'] = d['RBC1AAJ']
    d['assets'] = d['ASSET']
    d['core_dep'] = d['COREDEP'].fillna(0)
    d['net_income'] = d['NETINC']
    d['equity'] = d['EQ']
    d['mortgages'] = d.get('RCON1754', pd.Series(0, index=d.index))

    # RBC1AAJ is already a percentage — divide by 100
    d['T1R'] = d['tier1'] / 100.0
    d['LTD'] = d['loans'] / d['deposits']
    d['CBD'] = (d['cash'] / (d['deposits'] / 365)).clip(upper=300)
    d['BDR'] = ((d['deposits'] - d['core_dep']) / d['deposits']).clip(lower=0)

    # Filter out very small banks — ratios are unstable
    d = d[d['assets'] >= 50000]

    return d.dropna(subset=['LTD', 'T1R', 'CBD', 'BDR'])


def build_baseline(df):
    """Build 4-quarter rolling baseline per bank."""
    df = df.sort_values(['CERT', 'REPDTE'])
    for col in ['LTD', 'T1R', 'CBD', 'BDR']:
        df[f'{col}_baseline'] = (
            df.groupby('CERT')[col]
            .transform(lambda x: x.shift(1).rolling(4, min_periods=2).mean())
        )
        df[f'{col}_delta'] = df[col] - df[f'{col}_baseline']
    return df


# ── P2 additions — trend detection and days-to-threshold ─────────────────────

def compute_trend(series):
    """
    Returns slope direction: 'rising', 'falling', or 'stable'
    Uses last 4 quarters of data.
    """
    series = series.dropna().tail(4).values
    if len(series) < 2:
        return 'stable'
    x = np.arange(len(series))
    slope, _, _, _, _ = stats.linregress(x, series)
    if slope > 0.001:
        return 'rising'
    elif slope < -0.001:
        return 'falling'
    else:
        return 'stable'


def days_to_threshold(series, threshold, direction='above'):
    """
    Estimates how many days until the metric crosses the threshold.
    Uses linear regression on last 4 quarters (each quarter = 90 days).
    Returns None if not heading toward threshold.
    """
    series = series.dropna().tail(4).values
    if len(series) < 2:
        return None
    x = np.arange(len(series))
    slope, intercept, _, _, _ = stats.linregress(x, series)

    if slope == 0:
        return None

    quarters_to_threshold = (threshold - intercept) / slope
    current_quarter = len(series) - 1
    quarters_remaining = quarters_to_threshold - current_quarter

    if quarters_remaining <= 0:
        return 0  # already crossed

    days = round(quarters_remaining * 90)

    if direction == 'above' and slope > 0:
        return days
    elif direction == 'below' and slope < 0:
        return days
    return None


def enrich_with_trends(df):
    """
    Takes the ratios dataframe and adds trend and days-to-threshold columns.
    Called at the end of run_watch_agent() before returning.
    """
    df = df.copy().sort_values(['CERT', 'REPDTE'])

    ltd_trends = []
    t1r_trends = []
    cbd_trends = []
    days_ltd = []
    days_t1r = []
    days_cbd = []

    for cert, group in df.groupby('CERT'):
        n = len(group)
        for i in range(n):
            window = group.iloc[max(0, i - 3):i + 1]

            ltd_trends.append(compute_trend(window['LTD']))
            t1r_trends.append(compute_trend(window['T1R']))
            cbd_trends.append(compute_trend(
                window['CBD']) if 'CBD' in window.columns else 'stable')

            days_ltd.append(days_to_threshold(
                window['LTD'], threshold=1.0,  direction='above'))
            days_t1r.append(days_to_threshold(
                window['T1R'], threshold=0.06, direction='below'))
            days_cbd.append(days_to_threshold(
                window['CBD'], threshold=8,    direction='below') if 'CBD' in window.columns else None)

    df['LTD_TREND'] = ltd_trends
    df['T1R_TREND'] = t1r_trends
    df['CBD_TREND'] = cbd_trends
    df['DAYS_TO_LTD_THRESHOLD'] = days_ltd
    df['DAYS_TO_T1R_THRESHOLD'] = days_t1r
    df['DAYS_TO_CBD_THRESHOLD'] = days_cbd

    return df


# ── Main entry point ──────────────────────────────────────────────────────────

def run_watch_agent():
    """Main entry point — reads raw data, returns enriched dataframe."""
    fin = pd.read_csv("data/raw/mdi_financials.csv")
    mdis = pd.read_csv("data/raw/mdi_list.csv")

    print("Computing ratios...")
    ratios = compute_ratios(fin)

    print("Building baselines...")
    ratios = build_baseline(ratios)

    print("Merging bank names...")
    ratios = ratios.merge(
        mdis[['CERT', 'INSTNAME', 'CITY', 'STALP']],
        on='CERT', how='left'
    )

    print("Enriching with trends and days-to-threshold...")
    ratios = enrich_with_trends(ratios)

    ratios.to_csv("data/processed/mdi_ratios.csv", index=False)
    print(f"Saved {len(ratios)} rows to data/processed/mdi_ratios.csv")
    print(f"New columns added: LTD_TREND, T1R_TREND, CBD_TREND, "
          f"DAYS_TO_LTD_THRESHOLD, DAYS_TO_T1R_THRESHOLD, DAYS_TO_CBD_THRESHOLD")

    return ratios
