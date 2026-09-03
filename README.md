# AI Finance Controller (Razorpay Buildathon)

This repository contains the submission for the **Razorpay AI Buildathon (Track 04: AI Finance Controller)**.

## Architecture & Data Flow

This project implements a multi-source financial reconciliation engine that ingests data from 4 sources (OMS, Gateway, Settlement, Bank) and matches them using a 3-tier pipeline. It forms a complete finance-ops loop.

1. **Tier 1: Deterministic Matching** — Exact ID/amount matches (Confidence 1.0). **We intentionally do not use AI here** because deterministic logic is faster, cheaper, and provably correct for exact UTR and ID matches.
2. **Tier 2: Fuzzy Matching** — Date windows, amount tolerances, net-of-fee math (Confidence > 0.75). Again, pure heuristic code.
3. **Tier 3: AI Exception Investigation** — For the few records that fail both programmatic tiers, we use Google Gemini Structured Outputs to diagnose exceptions (Confidence > 0.80). This ensures we apply LLM reasoning *only* where traditional logic fails, minimizing token cost while maximizing automation.

Every decision is atomically logged to a local SQLite database (`audit_trail.db`) in WAL mode for full transparency.

## Honest Metrics

Against a 120-record synthetic ground truth batch (featuring deliberate edge cases like timing lags and fee variances):

* **Total Records Ingested**: 480 (across 4 sources)
* **Tier 1 Exact Matches**: 344 matches (Properly handles UTR-based batch aggregation)
* **Tier 2 Fuzzy Matches**: 1 match
* **Tier 3 AI Matches**: (AI is limited by the Gemini free-tier quota of 20 req/day. Once hit, it gracefully falls back to `manual_review`.)
* **Exceptions Flagged for Human Review**: 24 records
* **Processing Time**: ~6.0 seconds
* **Verified Correct Matches**: 200
* **Unverified Matches**: 145 (Expected: These are intermediate cross-source pairs like GW↔Recon that do not have an explicit ground truth row, but correctly matched transitively)
* **False Matches**: 0

## What Broke, and How We Fixed It (Failure Recovery)

*Our initial pipeline run reported 103 false matches. The AI could have easily been blamed, but we built a rigid audit trail to catch exactly this kind of failure.*

By dumping the decisions to an `exception_report.json`, we discovered two root causes. First, the evaluation harness was mapping arbitrary bank row IDs instead of Bank UTRs. Second, our Tier 1 deterministic logic was improperly attempting to match individual Recon payments against the *aggregated* batch settlement amount in the Bank file.

The fix required zero changes to the AI. We corrected the eval ID mapping and rewrote Tier 1 to properly group Recon records by UTR and sum their `net_amount` *before* comparing to the Bank statement. This single architectural fix brought our false match rate down to an honest **0**.

## Setup & Run

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Add your Gemini API key to .env

# 3. Run the pipeline and evaluate against ground truth
python evaluate.py
```

The detailed report will be saved to `results/report.html`, and a full CLI evaluation will be displayed in the terminal.
