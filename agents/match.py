from config import ANTHROPIC_API_KEY
import anthropic
import pandas as pd
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


os.makedirs("data/processed/briefs", exist_ok=True)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PROGRAMS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "programs.json"
)

with open(PROGRAMS_PATH, "r") as f:
    PROGRAMS = json.load(f)


def check_eligibility(alert_card, inst_row):
    """
    Checks which of the 3 federal programs the bank qualifies for.
    Returns list sorted by access speed — fastest first.
    """
    eligible = []
    assets = float(inst_row.get('ASSET', 0) or 0) * 1000
    fhlb = int(inst_row.get('FHLB_MEMBER', 0) or 0)
    cdfi = int(inst_row.get('CDFI_CERT', 0) or 0)

    for prog_id, prog in PROGRAMS.items():
        ok = True
        for req in prog.get('requires', []):
            if req == 'fhlb_member' and not fhlb:
                ok = False
            if req == 'cdfi_cert' and not cdfi:
                ok = False
        if ok:
            amount = estimate_amount(prog_id, prog, assets)
            eligible.append({
                **prog,
                'id': prog_id,
                'estimated_amount': amount
            })

    return sorted(eligible, key=lambda x: x['speed_days'])


def estimate_amount(prog_id, prog, assets):
    """Calculates maximum accessible funding for each program."""
    if prog_id == 'discount_window':
        return int(assets * prog.get('max_pct_assets', 0.30))
    elif prog_id == 'fhlb_advance':
        mortgages = assets * 0.30
        return int(mortgages * prog.get('max_pct_mortgages', 0.80))
    elif prog_id == 'cdfi_fund':
        return prog.get('max_amount', 5000000)
    return 0


def generate_brief(bank_name, program, alert_card, amount):
    """
    Calls Claude API to generate a CFO-ready application brief.
    Tailored to the specific bank's financial situation.
    """
    ltd_pct = round(float(alert_card.get('ltd', 0)) * 100, 1)
    t1r_pct = round(float(alert_card.get('t1r', 0)) * 100, 1)
    cbd = round(float(alert_card.get('cbd', 0)), 0)
    score = alert_card.get('risk_score', 0)
    severity = alert_card.get('severity', 'high').upper()
    city = alert_card.get('city', '')
    state = alert_card.get('state', '')
    days = alert_card.get('earliest_warning_days', None)
    days_str = f"{days} days" if days else "immediate action required"

    prompt = f"""You are a senior banking advisor helping a minority depository institution
apply for emergency federal liquidity support. Write a concise, professional
application brief that a CFO could submit today.

Bank: {bank_name} — {city}, {state}
Program: {program['name']}
Estimated funding access: ${amount:,.0f}
Program type: {program['type'].upper()}
Expected access time: {program['speed_days']} days

Current financial metrics:
  Loan-to-deposit ratio: {ltd_pct}% (danger threshold: 110%)
  Tier 1 capital ratio:  {t1r_pct}% (regulatory minimum: 6%)
  Cash buffer:           {cbd} days (warning threshold: 15 days)
  Overall risk score:    {score}/100 — {severity}
  Estimated days to threshold: {days_str}

Program details:
  Notes: {program.get('notes', '')}
  Application URL: {program.get('application_url', '')}
  Contact: {program.get('contact', '')}

Write a brief with exactly these 5 sections:
1. Situation summary (2 sentences — use specific numbers, no generic language)
2. Eligibility statement (cite the specific regulatory rule that qualifies this bank)
3. Amount requested and collateral or basis for the request
4. Submission steps (3-5 numbered steps, specific and actionable today)
5. Key contact, application URL, and estimated processing time

Hard requirements:
- Under 300 words total
- Use the actual bank name and actual dollar amounts throughout
- Sound like it was written by a banking professional not AI
- Be specific — a CFO should be able to act on this today
- Do not use phrases like it is crucial, in conclusion, or it is important to note"""

    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text


def save_brief(cert, results):
    """Saves generated briefs to disk for dashboard to display."""
    path = f"data/processed/briefs/{cert}.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    return path


def run_match_agent(alert_row, inst_row):
    """
    Main entry point — takes a flagged bank, returns matched programs and briefs.
    Called by main.py for each approved alert.
    """
    eligible = check_eligibility(alert_row, inst_row)

    if not eligible:
        name = alert_row.get('bank_name', alert_row.get('INSTNAME', 'Unknown'))
        print(f"    No eligible programs for {name}")
        return []

    results = []
    for prog in eligible[:2]:
        try:
            name = alert_row.get(
                'bank_name', alert_row.get('INSTNAME', 'Unknown'))
            alert_dict = (
                alert_row if isinstance(alert_row, dict)
                else alert_row.to_dict()
            )
            brief = generate_brief(
                bank_name=name,
                program=prog,
                alert_card=alert_dict,
                amount=prog['estimated_amount']
            )
            results.append({'program': prog, 'brief': brief})
            print(f"    Brief generated: {prog['name']}")
        except Exception as e:
            print(f"    Error generating brief for {prog['name']}: {e}")

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Match agent on Ponce Bank (CERT 31189)")
    print("=" * 60)

    with open("data/processed/approved_alerts.json") as f:
        alerts = json.load(f)

    ponce = next((a for a in alerts if a['cert'] == 31189), None)
    if not ponce:
        print("Ponce Bank not in alerts — using highest risk bank")
        ponce = alerts[0]

    mdis = pd.read_csv("data/raw/mdi_list.csv")
    inst_rows = mdis[mdis['CERT'] == ponce['cert']]

    if len(inst_rows) == 0:
        print(f"CERT {ponce['cert']} not in MDI list — using first MDI")
        inst = mdis.iloc[0]
    else:
        inst = inst_rows.iloc[0]

    print(f"\nBank:       {ponce.get('bank_name', inst['INSTNAME'])}")
    print(f"Location:   {ponce.get('city', '')}, {ponce.get('state', '')}")
    print(f"Risk score: {ponce['risk_score']} — {ponce['severity'].upper()}")
    print(f"LTD:        {round(ponce['ltd']*100, 1)}%")
    print(f"T1R:        {round(ponce['t1r']*100, 1)}%")
    print(f"CBD:        {ponce['cbd']} days")

    print("\nChecking eligibility...")
    eligible = check_eligibility(ponce, inst)
    print(f"Eligible programs: {len(eligible)}")
    for p in eligible:
        print(
            f"  - {p['name']} (${p['estimated_amount']:,.0f}, {p['speed_days']} days)")

    print("\nGenerating briefs...")
    results = run_match_agent(ponce, inst)

    if results:
        save_brief(ponce['cert'], results)
        print(f"\nGenerated {len(results)} briefs and saved to disk")
        print("\n" + "=" * 60)
        for r in results:
            print(f"\nPROGRAM: {r['program']['name']}")
            print(f"AMOUNT:  ${r['program']['estimated_amount']:,.0f}")
            print(f"\nBRIEF:\n{r['brief']}")
            print("=" * 60)
    else:
        print("\nNo briefs generated.")
        print("Check: does programs.json exist in project root?")
        print("Check: is ANTHROPIC_API_KEY set in config.py?")
