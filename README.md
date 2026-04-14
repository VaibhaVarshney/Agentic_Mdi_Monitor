# MDI Liquidity Monitor

AI-powered early warning system for 144 minority depository institutions (MDIs).

Detects liquidity stress **60–90 days before crisis** and automatically matches
at-risk banks to federal assistance programs (Fed Discount Window, FHLB advances,
CDFI grants), generating a ready-to-submit application brief for the bank's CFO.

---

## The problem

There are 144 minority-owned banks in the US. When one fails, the community
it serves loses its primary source of credit — often permanently. Federal
emergency programs exist to prevent this, but they live in PDFs on government
websites. Nobody is watching MDI liquidity in real time and connecting the dots.

---

## What this system does

1. **Watch** — reads FDIC Call Report data quarterly, computes liquidity ratios
2. **Warn** — flags banks 60–90 days before they hit regulatory danger thresholds  
3. **Match** — identifies which federal programs the bank qualifies for and
   generates a complete application brief for the CFO

---

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/mdi-liquidity-monitor.git
cd mdi-liquidity-monitor
pip install -r requirements.txt
cp config.example.py config.py
# Edit config.py and add your Anthropic API key
```

Download the data CSVs from Google Drive (link in team chat) into the `data/` folders.

---

## Run order (P1 runs these)

```bash
python get_mdi_list.py      # pull 144 MDIs from FDIC
python get_financials.py    # pull quarterly financial data
python compute_ratios.py    # compute ratios and risk scores
python get_highland.py      # pull back-test data
python verify_data.py       # confirm everything is correct
```

## Run full pipeline

```bash
python main.py
```

## Launch dashboard

```bash
streamlit run dashboard/app.py
```

---

## Data sources

- **FDIC BankFind API** — `banks.data.fdic.gov/api` — free, no key required
- **Federal Reserve** — Discount Window program terms
- **CDFI Fund** — grant eligibility and amounts
- **FFIEC CDR** — bulk Call Report data for historical back-testing

---

## Team

| Person | Role | File |
|--------|------|------|
| P1 | Data pipeline | `get_*.py`, `compute_ratios.py` |
| P2 | Watch agent | `agents/watch.py` |
| P3 | Warn agent | `agents/warn.py` |
| P4 | Match agent | `agents/match.py` |
| P5 | Dashboard + demo | `dashboard/app.py` |

---

## Key liquidity ratios

| Ratio | Formula | Flag threshold | Critical |
|-------|---------|---------------|----------|
| LTD (loan-to-deposit) | loans / deposits | > 0.90 | > 0.95 |
| T1R (Tier 1 capital) | tier1 capital / assets | < 7.5% | < 6.0% |
| CBD (cash buffer days) | cash / (deposits/365) | < 30 days | < 15 days |
| BDR (brokered deposit ratio) | brokered / deposits | > 10% | > 20% |

---

*UMD Agentic AI Challenge 2026*
