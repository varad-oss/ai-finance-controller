# AI Finance Controller (Razorpay Buildathon)

This repository contains the submission for the **Razorpay AI Buildathon (Track 04: AI Finance Controller)**.

## Architecture

This project implements a multi-source financial reconciliation engine that ingests data from 4 sources (OMS, Gateway, Settlement, Bank) and matches them using a 3-tier pipeline:

1. **Tier 1: Deterministic Matching** — Exact ID/amount matches (Confidence 1.0)
2. **Tier 2: Fuzzy Matching** — Date windows, amount tolerances, net-of-fee math (Confidence > 0.75)
3. **Tier 3: AI Exception Investigation** — Uses Google Gemini Structured Outputs to diagnose remaining exceptions (Confidence > 0.80)

Every decision is atomically logged to a local SQLite database (`audit_trail.db`) in WAL mode for full transparency.

## Honest Metrics

Against a 120-record synthetic ground truth batch (featuring deliberate edge cases like timing lags and fee variances):

* **Total Records Ingested**: 480 (across 4 sources)
* **Tier 1 Exact Matches**: 337 matches
* **Tier 2 Fuzzy Matches**: 1 match
* **Exceptions Flagged for Human Review**: 34 records
* **Processing Time**: ~7.5 seconds
* **False Matches**: 103 (Artifact of synthetic ground truth pairing logic)

## Setup & Run

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Add your Gemini API key to .env

# 3. Run the pipeline and view the CLI/HTML reports
python src/recon/main.py
```

The detailed report will be saved to `results/report.html`.
