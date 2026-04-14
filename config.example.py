# ============================================================
# Copy this file to config.py and fill in your Anthropic key
# NEVER commit config.py to GitHub
# ============================================================

ANTHROPIC_API_KEY = "sk-ant-YOUR_KEY_HERE"

THRESHOLDS = {
    "ltd_watch":    0.80,
    "ltd_warning":  0.90,
    "ltd_critical": 0.95,
    "t1_flag":      0.075,
    "t1_danger":    0.060,
    "cbd_watch":    30,
    "cbd_warning":  15,
    "bdr_watch":    0.10,
    "bdr_danger":   0.20,
}

WEIGHTS = {
    "ltd": 0.35,
    "t1":  0.35,
    "cbd": 0.20,
    "bdr": 0.10,
}

FDIC_BASE = "https://banks.data.fdic.gov/api"
