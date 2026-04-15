import requests
import pandas as pd

r = requests.get('https://banks.data.fdic.gov/api/financials',
                 params={
                     'filters': 'CERT:31559',
                     'fields': 'CERT,REPDTE,DEP,LNLSNET,CHBAL,RBC1AAJ,ASSET,COREDEP',
                     'limit': 30,
                     'sort_by': 'REPDTE',
                     'sort_order': 'DESC',
                     'output': 'json'
                 }).json()

rows = [d['data'] for d in r.get('data', [])]
df = pd.DataFrame(rows)
df = df.sort_values('REPDTE')

for col in ['DEP', 'LNLSNET', 'CHBAL', 'RBC1AAJ', 'ASSET', 'COREDEP']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

df['T1R'] = df['RBC1AAJ'] / 100.0
df['LTD'] = df['LNLSNET'] / df['DEP']
df['CBD'] = (df['CHBAL'] / (df['DEP'] / 365)).clip(upper=300)

print(f"Date range: {df['REPDTE'].min()} to {df['REPDTE'].max()}")
print(df[['REPDTE', 'LTD', 'T1R', 'CBD', 'ASSET']].to_string())
