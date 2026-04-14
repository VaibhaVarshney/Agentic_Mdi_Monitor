"""
agents/match.py — Match Agent
OWNED BY: P4
Takes a flagged bank, checks eligibility for federal programs,
estimates access amounts, and generates application brief via LLM.
"""

import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PROGRAMS = {
    "discount_window": {
        "name": "Federal Reserve Discount Window",
        "type": "loan",
        "speed_days": 2,
        "requires": [],           # any FDIC-insured bank qualifies
        "max_pct_assets": 0.30,
        "notes": "Collateral must be pre-pledged before crisis"
    },
    "fhlb_advance": {
        "name": "FHLB Advance",
        "type": "loan",
        "speed_days": 1,
        "requires": ["fhlb_member"],
        "max_pct_mortgages": 0.80,
        "notes": "Cheapest option, fastest access for members"
    },
    "cdfi_grant": {
        "name": "CDFI Fund Financial Assistance",
        "type": "grant",
        "speed_days": 180,
        "requires": ["cdfi_cert"],
        "max_amount": 5_000_000,
        "notes": "Free capital — no repayment required"
    },
}


def estimate_amount(bank_row, inst_row, prog):
    assets    = float(bank_row.get('assets', 0) or 0)
    mortgages = float(bank_row.get('mortgages', 0) or 0)
    if prog['id'] == 'discount_window':
        return int(assets * prog['max_pct_assets'])
    elif prog['id'] == 'fhlb_advance':
        return int(mortgages * prog.get('max_pct_mortgages', 0.8))
    elif prog['id'] == 'cdfi_grant':
        return prog['max_amount']
    return 0


def check_eligibility(bank_row, inst_row):
    eligible = []
    for prog_id, prog in PROGRAMS.items():
        ok = True
        for req in prog.get('requires', []):
            if req == 'fhlb_member' and not inst_row.get('FHLB_MEMBER', 0):
                ok = False
            if req == 'cdfi_cert' and not inst_row.get('CDFI_CERT', 0):
                ok = False
        if ok:
            amount = estimate_amount(bank_row, inst_row, {**prog, 'id': prog_id})
            eligible.append({**prog, 'id': prog_id, 'estimated_amount': amount})
    return sorted(eligible, key=lambda x: x['speed_days'])


def generate_brief(bank_name, program, bank_metrics, amount):
    prompt = f"""You are a banking advisor helping a minority depository institution
apply for emergency federal liquidity support.

Bank: {bank_name}
Program: {program['name']}
Estimated access amount: ${amount:,.0f}
Current financial metrics:
  - Loan-to-deposit ratio: {float(bank_metrics.get('LTD', 0)):.1%}
  - Tier 1 capital ratio:  {float(bank_metrics.get('T1R', 0)):.1%}
  - Cash buffer:           {float(bank_metrics.get('CBD', 0)):.0f} days
  - Risk score:            {bank_metrics.get('RISK_SCORE', 'N/A')}/100

Write a concise, professional application brief for the CFO with:
1. Situation summary (2 sentences)
2. Eligibility statement (cite the specific rule or requirement)
3. Amount requested and collateral or basis
4. Numbered submission steps (specific and actionable)
5. Key contact, deadline, and processing time

Under 300 words. Be factual and professional."""

    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text


def run_match_agent(alert_row, inst_row):
    eligible = check_eligibility(alert_row, inst_row)
    results = []
    for prog in eligible[:2]:   # top 2 programs only
        brief = generate_brief(
            bank_name=inst_row.get('INSTNAME', 'Unknown Bank'),
            program=prog,
            bank_metrics=alert_row,
            amount=prog['estimated_amount']
        )
        results.append({'program': prog, 'brief': brief})
    return results


# P4: Add your enhancements below this line
# Ideas: more programs, FHLB membership lookup, richer brief template
