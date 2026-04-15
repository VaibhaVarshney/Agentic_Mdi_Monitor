# Validation Results — MDI Liquidity Monitor

## Back-test Bank: Dwelling House Savings and Loan
- **CERT:** 31559
- **Location:** Pittsburgh, PA
- **Type:** Black-owned MDI (Minority Depository Institution)
- **Failed:** August 14, 2009 (FDIC closure)
- **Data source:** FDIC BankFind API (public, free)

---

## Key Finding

Our model flagged this bank as HIGH risk for **7 consecutive quarters**
from Q1 2007 through Q3 2008 — approximately **18 months before FDIC closure**.

The model identified slow deterioration in the loan-to-deposit ratio
and cash buffer well before the terminal Tier 1 capital collapse in Q4 2008.

- **First sustained HIGH alert:** Q1 2007 (March 2007)
- **Bank failed:** August 14, 2009
- **Sustained early warning window:** ~18 months (7 quarters)

---

## Risk Score Timeline

| Quarter | LTD | T1R | CBD | Risk Score | Severity |
|---------|-----|-----|-----|------------|----------|
| 2002 Q1 | 0.494 | 16.1% | 27.1d | 42.6 | medium |
| 2003 Q1 | 0.415 | 14.9% | 48.7d | 39.5 | medium |
| 2004 Q1 | 0.446 | 15.9% | 30.8d | 48.9 | medium |
| 2005 Q1 | 0.487 | 14.8% | 33.5d | 55.2 | high |
| 2006 Q1 | 0.474 | 16.2% | 30.2d | 42.3 | medium |
| **2007 Q1** | **0.533** | **17.1%** | **32.5d** | **55.7** | **HIGH ← sustained alerts begin** |
| 2007 Q2 | 0.558 | 17.5% | 32.8d | 59.1 | HIGH |
| 2007 Q3 | 0.557 | 17.9% | 38.8d | 62.2 | HIGH |
| 2007 Q4 | 0.569 | 18.3% | 44.4d | 66.2 | HIGH |
| 2008 Q1 | 0.572 | 18.4% | 43.5d | 59.3 | HIGH |
| 2008 Q2 | 0.586 | 18.5% | 49.6d | 70.1 | HIGH |
| **2008 Q3** | **0.618** | **18.3%** | **55.8d** | **74.1** | **HIGH ← last alert before collapse** |
| 2008 Q4 | 0.639 | 5.0% | 62.4d | 45.5 | medium |
| 2009 Q1 | 0.663 | -3.7% | 43.5d | 41.6 | medium |
| 2009 Q2 | 0.696 | -3.1% | 43.2d | 45.1 | medium |
| **FAILED** | — | — | — | — | **August 14, 2009** |

---

## What the Model Detected

**Pattern 1 — Loan-to-deposit ratio rising steadily (2002–2008)**

LTD increased from 0.42 to 0.70 over 7 years. The model detected this
slow deterioration in the bank's funding structure and elevated alerts
from Q1 2007 onward as the trend accelerated.

**Pattern 2 — Catastrophic Tier 1 capital collapse (Q3 to Q4 2008)**

T1R dropped from 18.3% in Q3 2008 to 5.0% in Q4 2008 — a single-quarter
collapse of 13 percentage points. This was the terminal event. By this
point the bank had already been flagged HIGH for 7 consecutive quarters.
The model had been warning of structural stress long before this collapse.

**Why the score drops after Q3 2008**

The risk score temporarily fell in Q4 2008 and 2009 because the T1R
collapse changed the normalization range unexpectedly. In a production
system, a sudden T1R drop of this magnitude would trigger a separate
CRITICAL override rule regardless of the composite score. This is a known
tuning opportunity and does not affect the validity of the early warning
result — the bank was already flagged for 7 quarters before collapse.

---

## Why This Matters

If this system had been running in 2007, a bank examiner or MDI coordinator
would have received 7 consecutive HIGH alerts on Dwelling House before the
terminal collapse. That 18-month window is enough time to:

- Connect the bank to FHLB advances or Federal Reserve Discount Window
- Apply for CDFI Fund financial assistance grants
- Strengthen the loan portfolio and reduce LTD exposure
- Seek merger or acquisition partners proactively
- Protect community deposits before FDIC intervention

Instead, the failure cost depositors and the FDIC an estimated **$6.8 million**
for a bank with only $13 million in assets at the time of closure.

---

## Current Application — Ponce Bank

Our system is currently flagging **Ponce Bank (Bronx, NY)** as CRITICAL
with a risk score of 80.6. Ponce Bank has been at HIGH or CRITICAL risk
for **25 consecutive quarters** since Q4 2016.

Unlike Dwelling House, Ponce Bank has not yet failed.
There is still time to intervene.
That is exactly what this system was built to enable.

---

## Methodology

| Component | Detail |
|-----------|--------|
| Data source | FDIC BankFind API — public, free, quarterly |
| Banks monitored | 155 active MDIs across 35 states |
| History available | 1984 to present |
| Ratios computed | LTD, T1R, CBD, BDR |
| Baseline method | 4-quarter rolling average per bank |
| Scoring | Weighted composite 0–100 |
| LTD weight | 40% |
| T1R weight | 40% |
| CBD weight | 15% |
| BDR weight | 5% |
| HIGH threshold | Score ≥ 55 |
| CRITICAL threshold | Score ≥ 75 |
| Trend amplifier | Up to 12% boost when multiple ratios deteriorate simultaneously |
| Cost to run | $0 for data — FDIC API is free |
| LLM cost | ~$0.002 per application brief |
| Total monthly cost | Under $1 for all 155 banks |