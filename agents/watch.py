"""
agents/watch.py — Watch Agent
OWNED BY: P2
Reads raw FDIC financial data, computes liquidity ratios,
builds rolling baselines, and outputs scored data.
"""

import pandas as pd
import numpy as np
import os
from config import WEIGHTS

os.makedirs("data/processed", exist_ok=True)


def normalize(val, lo, hi, invert=False):
    try:
        n = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
        return 1.0 - n if invert else n
    except:
        return 0.0


def compute_ratios(df):
    """Compute the 4 core liquidity ratios from raw RCON fields."""
    d = df.copy()
    numeric_cols = [
        'RCON2200', 'RCON2122', 'RCON0010', 'RCON8274',
        'RCON2170', 'RCONB558', 'RCONB559', 'RCON4074',
        'RCON4230', 'RCON1754'
    ]
    for col in numeric_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors='coerce')

    d['deposits']  = d['RCON2200']
    d['loans']     = d['RCON2122']
    d['cash']      = d['RCON0010']
    d['tier1']     = d['RCON8274']
    d['assets']    = d['RCON2170']
    d['brokered']  = d['RCONB558'].fillna(0) + d['RCONB559'].fillna(0)
    d['mortgages'] = d['RCON1754'].fillna(0)

    d['LTD'] = d['loans']    / d['deposits']
    d['T1R'] = d['tier1']    / d['assets']
    d['CBD'] = d['cash']     / (d['deposits'] / 365)
    d['BDR'] = d['brokered'] / d['deposits']

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


def days_to_threshold(bank_df, col, threshold, direction='above'):
    """Estimate days until ratio crosses threshold using linear trend."""
    try:
        from sklearn.linear_model import LinearRegression
        recent = bank_df.tail(4)[col].dropna().values
        if len(recent) < 2:
            return None
        X = np.arange(len(recent)).reshape(-1, 1)
        model = LinearRegression().fit(X, recent)
        slope = model.coef_[0]
        current = recent[-1]
        if direction == 'above' and slope <= 0:
            return None
        if direction == 'below' and slope >= 0:
            return None
        quarters_away = (threshold - current) / slope
        return int(max(0, quarters_away * 90))
    except:
        return None


def run_watch_agent():
    """Main entry point — reads raw data, returns scored dataframe."""
    fin  = pd.read_csv("data/raw/mdi_financials.csv")
    mdis = pd.read_csv("data/raw/mdi_list.csv")

    ratios = compute_ratios(fin)
    ratios = build_baseline(ratios)
    ratios = ratios.merge(
        mdis[['CERT', 'INSTNAME', 'CITY', 'STALP']],
        on='CERT', how='left'
    )
    ratios.to_csv("data/processed/mdi_ratios.csv", index=False)
    return ratios


# P2: Add your enhancements below this line
# Ideas: trend visualization, anomaly flags, per-bank alerts
