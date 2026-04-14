import requests
import pandas as pd
import io
import os

os.makedirs("data/raw", exist_ok=True)

print("=" * 50)
print("STEP 1: Pulling MDI list from FDIC official Excel")
print("=" * 50)

url = "https://www.fdic.gov/minority-depository-institutions-program/fourth-quarter-2025.xlsx"

print("Downloading official FDIC MDI Excel file...")
response = requests.get(url, timeout=60)

if response.status_code != 200:
    print(f"ERROR: {response.status_code}")
    exit()

# Row 0 is the title, row 1 is the real header
df = pd.read_excel(io.BytesIO(response.content), header=1)

# Clean column names
df.columns = df.columns.str.strip().str.replace('\n', ' ')

# Drop empty rows
df = df.dropna(subset=['CERT'])

# Rename to clean names using EXACT column names from the Excel
df = df.rename(columns={
    'NAME':                                          'INSTNAME',
    'STATE':                                         'STALP',
    'EST. DATE':                                     'EST_DATE',
    'MINORITY STATUS Alpha':                         'MINORITY_ALPHA',
    'MINORITY STATUS  BY OWNERSHIP TYPE Numeric':    'MINORITY_NUM',
    'FDIC REGION':                                   'FDIC_REGION',
    'TOTAL ASSETS  ($000)':                          'ASSET',
})

# Convert CERT to integer
df['CERT'] = pd.to_numeric(df['CERT'], errors='coerce')
df = df.dropna(subset=['CERT'])
df['CERT'] = df['CERT'].astype(int)

# Add FHLB and CDFI flags
df['FHLB_MEMBER'] = 0
df['CDFI_CERT'] = 0

known_fhlb = [34472, 18409, 12368, 19871, 22490]
known_cdfi = [34472, 32990, 22490, 33383, 18409]

df.loc[df['CERT'].isin(known_fhlb), 'FHLB_MEMBER'] = 1
df.loc[df['CERT'].isin(known_cdfi), 'CDFI_CERT'] = 1

df.to_csv("data/raw/mdi_list.csv", index=False)

print(f"\nMDIs saved: {len(df)}")
print(f"\nSample:")
print(df[['CERT', 'INSTNAME', 'CITY', 'STALP', 'MINORITY_ALPHA', 'ASSET']].head(
    10).to_string(index=False))
print(f"\nMinority type breakdown:")
print(df['MINORITY_ALPHA'].value_counts().to_string())
print(f"\nFHLB members: {df['FHLB_MEMBER'].sum()}")
print(f"CDFI certified: {df['CDFI_CERT'].sum()}")
print(f"\nSaved: data/raw/mdi_list.csv")
print("All good! Run next: python get_financials.py")
