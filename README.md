# AI Finance Controller (Razorpay Buildathon)

This repository contains the submission for the **Razorpay AI Buildathon (Track 04: AI Finance Controller)**.

## Architecture & Data Flow

This project implements a multi-source financial reconciliation engine that ingests data from 4 sources (OMS, Gateway, Settlement, Bank) and matches them using a 3-tier pipeline. It forms a complete finance-ops loop.

1. **Tier 1: Deterministic Matching** — Exact ID/amount matches (Confidence 1.0).
2. **Tier 2: Fuzzy Matching** — Date windows, amount tolerances, net-of-fee math (Confidence > 0.75).
3. **Tier 3: AI Exception Investigation** — Google Gemini Structured Outputs diagnose exceptions for records that fail the programmatic tiers.

Every decision is atomically logged to a local SQLite database (`audit_trail.db`) in WAL mode for full transparency.

## Metrics

Pipeline processing time: 707 seconds
Records ingested: 480
Total matches made: 348
Verified correct matches: 290
False matches (wrong pair): 10
Exception leakage: 42 leaked matches (from 20 ground-truth exception records)
Unverified matches: 6
Exceptions flagged for human review: 21

### Match Tiers
Tier 1 Exact Matches: 344
Tier 2 Fuzzy Matches: 4
Tier 3 AI Matches: 0 (0 matches made from 21 Gemini API calls)

### Failure Recovery (What Broke)
- **OMS ID Corruption**: The OMS source extractor attempted to read an `id` column that did not exist in the CSV, returning `"None"` for all OMS records. Fixed by using the `order_ref` column.
- **Exception Leakage**: Ground-truth exception records (like missing bank entries and duplicate payments) contained valid fields that matched correctly in the engine, but the evaluator did not detect that they were meant to be exceptions. The evaluator was rewritten to cross-reference matched IDs against a known exceptions list.
- **AI Rate Limits**: The Tier 3 Gemini API hit 429 and 503 errors during bulk exception processing. Fixed by lowering `TIER3_MAX_LLM_CALLS` to 5.

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
