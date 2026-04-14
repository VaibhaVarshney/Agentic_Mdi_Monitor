"""
dashboard/app.py — Streamlit Dashboard
OWNED BY: P5
Run with: streamlit run dashboard/app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="MDI Liquidity Monitor",
    layout="wide",
    page_icon="🏦"
)

st.title("MDI Liquidity Monitor")
st.caption("Early warning system for 144 minority depository institutions")

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    latest  = pd.read_csv("data/processed/mdi_latest.csv")
    ratios  = pd.read_csv("data/processed/mdi_ratios.csv")
    alerts  = pd.read_csv("data/processed/mdi_alerts.csv")
    mdis    = pd.read_csv("data/raw/mdi_list.csv")
    highland = pd.read_csv("data/backtest/highland_scored.csv")
    return latest, ratios, alerts, mdis, highland

try:
    latest, ratios, alerts, mdis, highland = load_data()
except FileNotFoundError as e:
    st.error(f"Data not found: {e}\nRun: python get_mdi_list.py → python get_financials.py → python compute_ratios.py")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total MDIs monitored", len(latest))
col2.metric("Critical alerts",
            int((alerts['SEVERITY'] == 'critical').sum()))
col3.metric("High alerts",
            int((alerts['SEVERITY'] == 'high').sum()))
col4.metric("Healthy banks",
            int(latest['SEVERITY'].isin(['low', 'medium']).sum()))

st.divider()

# ── Main bank table ───────────────────────────────────────────────────────────
st.subheader("All 144 MDIs — current risk status")

SCOLOR = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
display = latest.copy()
display['Status'] = display['SEVERITY'].map(SCOLOR)
display['LTD %']  = (display['LTD'] * 100).round(1).astype(str) + '%'
display['T1R %']  = (display['T1R'] * 100).round(1).astype(str) + '%'
display['CBD']    = display['CBD'].round(0).astype(int).astype(str) + 'd'

st.dataframe(
    display[['Status', 'INSTNAME', 'CITY', 'STALP',
             'RISK_SCORE', 'LTD %', 'T1R %', 'CBD']]\
        .sort_values('RISK_SCORE', ascending=False)\
        .rename(columns={
            'INSTNAME': 'Bank', 'CITY': 'City',
            'STALP': 'State', 'RISK_SCORE': 'Risk score'
        }),
    use_container_width=True,
    hide_index=True
)

st.divider()

# ── Bank detail panel ─────────────────────────────────────────────────────────
st.subheader("Bank detail")
selected = st.selectbox("Select a bank",
    latest.sort_values('RISK_SCORE', ascending=False)['INSTNAME'].tolist())

cert = int(latest[latest['INSTNAME'] == selected]['CERT'].values[0])
history = ratios[ratios['CERT'] == cert].sort_values('REPDTE')
bank_latest = latest[latest['CERT'] == cert].iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Risk score", f"{bank_latest['RISK_SCORE']}/100")
c2.metric("LTD ratio",  f"{bank_latest['LTD']:.1%}")
c3.metric("T1R",        f"{bank_latest['T1R']:.1%}")
c4.metric("Cash buffer",f"{bank_latest['CBD']:.0f} days")

fig = go.Figure()
fig.add_trace(go.Scatter(x=history['REPDTE'], y=history['LTD'],
    name='LTD ratio', line=dict(color='#E24B4A', width=2)))
fig.add_trace(go.Scatter(x=history['REPDTE'], y=history['T1R'],
    name='T1R', line=dict(color='#378ADD', width=2)))
fig.add_hline(y=0.95, line_dash="dash", line_color="#E24B4A",
    annotation_text="LTD critical (0.95)")
fig.add_hline(y=0.075, line_dash="dash", line_color="#EF9F27",
    annotation_text="T1R flag (7.5%)")
fig.update_layout(title=f"{selected} — ratio trends",
    xaxis_title="Quarter", yaxis_title="Ratio", height=350)
st.plotly_chart(fig, use_container_width=True)

# ── Match agent UI ────────────────────────────────────────────────────────────
if cert in alerts['CERT'].values:
    alert_row = alerts[alerts['CERT'] == cert].iloc[0]
    st.warning(f"Bank flagged: Risk score {alert_row['RISK_SCORE']:.0f} — {alert_row['SEVERITY'].upper()}")

    if st.button("Generate federal program match + application brief"):
        inst_row = mdis[mdis['CERT'] == cert].iloc[0]
        with st.spinner("Matching programs and drafting application brief..."):
            from agents.match import run_match_agent
            results = run_match_agent(alert_row, inst_row)
        for r in results:
            p = r['program']
            with st.expander(
                f"{p['name']} — ${p['estimated_amount']:,.0f} "
                f"({p['type']}, {p['speed_days']} day access)"
            ):
                st.markdown(r['brief'])

st.divider()

# ── Highland back-test ────────────────────────────────────────────────────────
st.subheader("Highland Community Bank — back-test")
st.caption("Failed January 2023. Did our system flag it early enough?")

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=highland['REPDTE'], y=highland['RISK_SCORE'],
    name='Risk score', line=dict(color='#7F77DD', width=2.5)))
fig2.add_hline(y=55, line_dash="dash", line_color="#EF9F27",
    annotation_text="HIGH threshold (55)")
fig2.add_hline(y=75, line_dash="dash", line_color="#E24B4A",
    annotation_text="CRITICAL threshold (75)")
fig2.add_vrect(x0="20221201", x1="20230201",
    fillcolor="#E24B4A", opacity=0.12,
    annotation_text="FAILURE Jan 2023")
fig2.update_layout(title="Highland risk score over time",
    xaxis_title="Quarter", yaxis_title="Risk score (0-100)", height=350)
st.plotly_chart(fig2, use_container_width=True)

first_high = highland[highland['SEVERITY'].isin(['high','critical'])]['REPDTE'].min()
if first_high:
    qtrs = len(highland[(highland['REPDTE'] >= first_high) &
                         (highland['REPDTE'] < '20230101')])
    st.success(f"Alert would have fired at {first_high} — "
               f"{qtrs} quarters ({qtrs * 90} days) before failure.")

# P5: Add your enhancements below this line
# Ideas: map view, export to PDF, email alert simulation
