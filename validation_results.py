import pandas as pd
import numpy as np
from scipy import stats

data = {
    'REPDTE': [20020331, 20020630, 20020930, 20021231, 20030331, 20030630, 20030930,
               20031231, 20040331, 20040630, 20040930, 20041231, 20050331, 20050630,
               20050930, 20051231, 20060331, 20060630, 20060930, 20061231, 20070331,
               20070630, 20070930, 20071231, 20080331, 20080630, 20080930, 20081231,
               20090331, 20090630],
    'LTD':    [0.4937, 0.4715, 0.4446, 0.4173, 0.4154, 0.4236, 0.4324, 0.4239,
               0.4460, 0.4656, 0.4657, 0.4744, 0.4867, 0.4811, 0.4930, 0.4801,
               0.4743, 0.4942, 0.5133, 0.5246, 0.5327, 0.5579, 0.5567, 0.5687,
               0.5719, 0.5860, 0.6179, 0.6393, 0.6627, 0.6961],
    'T1R':    [0.1609, 0.1481, 0.1501, 0.1463, 0.1488, 0.1512, 0.1551, 0.1578,
               0.1591, 0.1632, 0.1606, 0.1557, 0.1478, 0.1596, 0.1662, 0.1629,
               0.1622, 0.1634, 0.1659, 0.1675, 0.1709, 0.1746, 0.1790, 0.1833,
               0.1838, 0.1855, 0.1827, 0.0503, -0.0374, -0.0311],
    'CBD':    [27.1, 29.2, 28.0, 62.1, 48.7, 52.7, 50.1, 32.4, 30.8, 41.9,
               38.5, 45.6, 33.5, 32.5, 23.6, 29.5, 30.2, 30.6, 30.2, 33.6,
               32.5, 32.8, 38.8, 44.4, 43.5, 49.6, 55.8, 62.4, 43.5, 43.2],
}

df = pd.DataFrame(data)
df = df.sort_values('REPDTE').reset_index(drop=True)

# Rolling baseline
for col in ['LTD', 'T1R', 'CBD']:
    df[f'{col}_baseline'] = df[col].shift(1).rolling(4, min_periods=2).mean()
    df[f'{col}_delta'] = df[col] - df[f'{col}_baseline']

# Risk score


def normalize(val, lo, hi, invert=False):
    n = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
    return 1.0 - n if invert else n


def risk(row):
    base = (
        0.40 * normalize(row['LTD'], 0.40, 0.90) +
        0.40 * normalize(row['T1R'], 0.20, 0.04, invert=True) +
        0.20 * normalize(row['CBD'], 80,   10,   invert=True)
    ) * 100
    bad = sum([
        row.get('LTD_delta', 0) > 0.02,
        row.get('T1R_delta', 0) < -0.005,
        row.get('CBD_delta', 0) < -3,
    ])
    return round(min(100.0, base * (1 + bad * 0.12)), 1)


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

print("Dwelling House Savings and Loan — Risk History")
print(f"{'Quarter':<12} {'LTD':>6} {'T1R':>7} {'CBD':>7} {'Score':>6} {'Severity'}")
print("-" * 60)
for _, row in df.iterrows():
    marker = " ← ALERT" if row['SEVERITY'] in ['high', 'critical'] else ""
    print(f"{row['REPDTE']:<12} {row['LTD']:>6.3f} {row['T1R']:>7.3f} "
          f"{row['CBD']:>7.1f} {row['RISK_SCORE']:>6.1f} {row['SEVERITY']}{marker}")

flagged = df[df['SEVERITY'].isin(['high', 'critical'])]
if len(flagged) > 0:
    first = flagged['REPDTE'].min()
    before_failure = df[
        (df['REPDTE'] >= first) &
        (df['REPDTE'] < 20090814)
    ]
    print(f"\nFirst alert fires:     {first}")
    print(f"Bank failed:           August 14, 2009")
    print(f"Quarters of warning:   {len(before_failure)}")
    print(f"Days of early warning: ~{len(before_failure) * 90}")
