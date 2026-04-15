"""
agents/warn.py — Warn Agent
OWNED BY: Aadya (P3)
Takes ratio data from Watch agent, assigns risk scores,
generates alert cards, runs human review gate,
saves approved alerts for Match agent and Dashboard.
"""

import pandas as pd
import json
import os
from config import WEIGHTS, THRESHOLDS

os.makedirs("data/processed", exist_ok=True)


def normalize(val, lo, hi, invert=False):
    try:
        n = max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))
        return 1.0 - n if invert else n
    except:
        return 0.0


def compute_risk_score(row):
    try:
        cbd_capped = min(float(row['CBD']), 300)
        base = (
            WEIGHTS['ltd'] * normalize(row['LTD'], 0.70, 1.10) +
            WEIGHTS['t1'] * normalize(row['T1R'], 0.20, 0.06, invert=True) +
            WEIGHTS['cbd'] * normalize(cbd_capped,  120,  8,   invert=True) +
            WEIGHTS['bdr'] * normalize(row['BDR'], 0.05, 0.40)
        ) * 100
        deteriorating = sum([
            row.get('LTD_delta', 0) > 0.04,
            row.get('T1R_delta', 0) < -0.008,
            row.get('CBD_delta', 0) < -4,
        ])
        return round(min(100.0, base * (1 + deteriorating * 0.12)), 1)
    except:
        return 0.0


def assign_severity(score):
    if score < 30:
        return "low"
    if score < 55:
        return "medium"
    if score < 75:
        return "high"
    return "critical"


def generate_alert_card(row):
    """
    Generates a structured alert card for a flagged bank.
    This is what gets shown on the dashboard and sent to the CFO.
    """
    days_ltd = row.get('DAYS_TO_LTD_THRESHOLD', None)
    days_t1r = row.get('DAYS_TO_T1R_THRESHOLD', None)

    if days_ltd is not None and not pd.isna(days_ltd):
        days_ltd = int(days_ltd)
    else:
        days_ltd = None

    if days_t1r is not None and not pd.isna(days_t1r):
        days_t1r = int(days_t1r)
    else:
        days_t1r = None

    earliest_warning = None
    if days_ltd is not None and days_t1r is not None:
        earliest_warning = min(days_ltd, days_t1r)
    elif days_ltd is not None:
        earliest_warning = days_ltd
    elif days_t1r is not None:
        earliest_warning = days_t1r

    return {
        "cert":               int(row['CERT']),
        "bank_name":          str(row.get('INSTNAME', 'Unknown')),
        "city":               str(row.get('CITY', '')),
        "state":              str(row.get('STALP', '')),
        "risk_score":         round(float(row['RISK_SCORE']), 1),
        "severity":           str(row['SEVERITY']),
        "ltd":                round(float(row['LTD']), 3),
        "t1r":                round(float(row['T1R']), 3),
        "cbd":                round(float(row['CBD']), 1),
        "bdr":                round(float(row.get('BDR', 0)), 3),
        "ltd_trend":          str(row.get('LTD_TREND', 'stable')),
        "t1r_trend":          str(row.get('T1R_TREND', 'stable')),
        "cbd_trend":          str(row.get('CBD_TREND', 'stable')),
        "days_to_ltd_danger": days_ltd,
        "days_to_t1r_danger": days_t1r,
        "earliest_warning_days": earliest_warning,
        "ltd_delta":          round(float(row.get('LTD_delta', 0)), 4),
        "t1r_delta":          round(float(row.get('T1R_delta', 0)), 4),
        "alert_date":         pd.Timestamp.today().strftime('%Y-%m-%d'),
        "human_reviewed":     False,
        "approved":           False,
    }


def human_review_gate(alert_card, demo_mode=True):
    """
    Human-in-the-loop approval gate.
    This is a critical agentic design decision — the system cannot
    escalate to the Match agent without human confirmation.

    In demo mode: auto-approves for smooth video recording.
    In production: would send email to analyst and wait for response.
    """
    if demo_mode:
        alert_card['human_reviewed'] = True
        alert_card['approved'] = True
        return True

    print(f"\n{'='*50}")
    print(f"ALERT REQUIRES HUMAN REVIEW")
    print(f"{'='*50}")
    print(f"Bank:       {alert_card['bank_name']} ({alert_card['state']})")
    print(
        f"Risk score: {alert_card['risk_score']} — {alert_card['severity'].upper()}")
    print(f"LTD:        {alert_card['ltd']} ({alert_card['ltd_trend']})")
    print(f"T1R:        {alert_card['t1r']} ({alert_card['t1r_trend']})")
    print(f"CBD:        {alert_card['cbd']} days ({alert_card['cbd_trend']})")
    if alert_card['earliest_warning_days']:
        print(
            f"Estimated days to threshold: {alert_card['earliest_warning_days']}")
    print(f"{'='*50}")
    decision = input(
        "Approve this alert for program matching? (y/n): ").strip().lower()
    alert_card['human_reviewed'] = True
    alert_card['approved'] = decision == 'y'
    return alert_card['approved']


def run_warn_agent(ratios_df=None, demo_mode=True):
    """
    Main entry point for the Warn agent.
    Reads ratio data, scores all banks, generates alert cards,
    runs human review gate, saves approved alerts.
    """
    if ratios_df is None:
        ratios_df = pd.read_csv("data/processed/mdi_ratios.csv")

    ratios_df = ratios_df.copy()

    # Score all banks
    ratios_df['RISK_SCORE'] = ratios_df.apply(compute_risk_score, axis=1)
    ratios_df['SEVERITY'] = ratios_df['RISK_SCORE'].apply(assign_severity)

    # Get latest quarter per bank
    latest = ratios_df.sort_values('REPDTE').groupby('CERT').tail(1).copy()
    latest.to_csv("data/processed/mdi_latest.csv", index=False)

    # Flag high and critical banks
    flagged = latest[
        latest['SEVERITY'].isin(['high', 'critical'])
    ].copy().sort_values('RISK_SCORE', ascending=False)
    flagged.to_csv("data/processed/mdi_alerts.csv", index=False)

    print(f"  Total banks scored: {len(latest)}")
    print(f"  Flagged (high+critical): {len(flagged)}")
    print(f"    Critical: {(flagged['SEVERITY'] == 'critical').sum()}")
    print(f"    High:     {(flagged['SEVERITY'] == 'high').sum()}")

    # Generate alert cards and run through human review gate
    approved = []
    for _, row in flagged.iterrows():
        card = generate_alert_card(row)
        if human_review_gate(card, demo_mode=demo_mode):
            approved.append(card)

    # Save approved alerts as JSON for Match agent and Dashboard
    with open("data/processed/approved_alerts.json", "w") as f:
        json.dump(approved, f, indent=2, default=str)

    print(f"  Approved alerts saved: {len(approved)}")
    print(f"  Saved: data/processed/approved_alerts.json")

    return flagged


if __name__ == "__main__":
    print("Running Warn agent standalone...")
    ratios = pd.read_csv("data/processed/mdi_ratios.csv")
    alerts = run_warn_agent(ratios, demo_mode=True)
    print("\nTop 5 flagged banks:")
    print(alerts[['INSTNAME', 'CITY', 'STALP',
                  'RISK_SCORE', 'SEVERITY', 'LTD', 'T1R', 'CBD'
                  ]].head().round(3).to_string(index=False))
