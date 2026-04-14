import requests
import pandas as pd
import os
import time

os.makedirs("data/raw", exist_ok=True)

print("=" * 50)
print("STEP 2: Pulling MDI financial data from FDIC")
print("=" * 50)

mdis = pd.read_csv("data/raw/mdi_list.csv")
cert_list = mdis['CERT'].astype(int).tolist()
print(f"Loaded {len(cert_list)} MDIs from mdi_list.csv")

# Correct field names for FDIC BankFind API
FIELDS = [
    "CERT", "REPDTE",
    "DEP",       # total deposits
    "LNLSNET",   # net loans and leases
    "CHBAL",     # cash and balances due from banks
    "RBC1AAJ",   # Tier 1 capital
    "ASSET",     # total assets
    "COREDEP",   # core deposits (used for funding stability)
    "NETINC",    # net income
    "LNLSDEPR",  # loan loss reserves
    "LNLSNTV",   # total loans gross
    "EQ",        # total equity
    "RBCRWAJ",   # risk-weighted assets
    "INTINC",    # interest income
    "NONII",     # non-interest income
]


def pull_batch(certs, batch_num, total):
    cert_filter = "(" + " OR ".join(str(c) for c in certs) + ")"
    params = {
        "filters":  f"CERT:{cert_filter}",
        "fields":   ",".join(FIELDS),
        "limit":    2000,
        "sort_by":  "REPDTE",
        "sort_order": "DESC",
        "output":   "json"
    }
    print(f"  Batch {batch_num}/{total} ({len(certs)} banks)...", end=" ")
    r = requests.get(
        "https://banks.data.fdic.gov/api/financials",
        params=params,
        timeout=90
    )
    if r.status_code != 200:
        print(f"ERROR {r.status_code}")
        return []
    data = r.json().get('data', [])
    print(f"{len(data)} rows")
    return [d['data'] for d in data]


BATCH_SIZE = 30
batches = [cert_list[i:i+BATCH_SIZE]
           for i in range(0, len(cert_list), BATCH_SIZE)]

print(f"\nPulling in {len(batches)} batches of {BATCH_SIZE}...")
all_rows = []
for i, batch in enumerate(batches):
    rows = pull_batch(batch, i+1, len(batches))
    all_rows.extend(rows)
    time.sleep(0.5)

df = pd.DataFrame(all_rows)

if df.empty:
    print("ERROR: No data returned")
    exit()

print(f"\nTotal rows: {len(df)}")
print(f"Banks covered: {df['CERT'].nunique()}")
print(f"Date range: {df['REPDTE'].min()} to {df['REPDTE'].max()}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nSample row:")
print(df.iloc[0].to_string())

df.to_csv("data/raw/mdi_financials.csv", index=False)
print(f"\nSaved: data/raw/mdi_financials.csv")
print("Run next: python compute_ratios.py")
