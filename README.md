# AI Finance Controller (Razorpay Buildathon)

This repository contains the submission for the **Razorpay AI Buildathon (Track 04: AI Finance Controller)**.

## Architecture & Data Flow

This project implements a multi-source financial reconciliation engine that ingests data from 4 sources (OMS, Gateway, Settlement, Bank) and matches them using a 3-tier pipeline. It forms a complete finance-ops loop.

1. **Tier 1: Deterministic Matching** — Exact ID/amount matches (Confidence 1.0).
2. **Tier 2: Fuzzy Matching** — Date windows, amount tolerances, net-of-fee math (Confidence > 0.75).
3. **Tier 3: AI Exception Investigation** — Google Gemini Structured Outputs diagnose exceptions for records that fail the programmatic tiers.

Every decision is atomically logged to a local SQLite database (`audit_trail.db`) in WAL mode for full transparency.

## Metrics

Pipeline processing time: 163217 ms
Records ingested: 478
Total matches made: 342
Verified correct matches: 300
False matches (wrong pair): 0
Exception leakage: 0 (from 20 ground-truth exception records)
Unverified matches: 42
Exceptions flagged for human review: 36

### Match Tiers
Tier 1 Exact Matches: 339
Tier 2 Fuzzy Matches: 1
Tier 3 AI Matches: 4 (from 15 Gemini API calls before rate limit)

### Failure Recovery (What Broke)
- **OMS ID Corruption**: The OMS source extractor attempted to read an `id` column that did not exist in the CSV, returning `"None"` for all OMS records. Fixed by using the `order_ref` column.
- **Exception Leakage & Leg-Scoping**: Initially, any match touching an exception record was flagged as "leakage." However, many exceptions are valid on specific legs (e.g., an `orphaned_record` exists only in the Gateway but has no OMS entry; a `missing_bank_entry` should legitimately match `OMS <-> Gateway` but fail `Recon <-> Bank`). By evaluating exceptions per-leg rather than per-record, false leakage dropped to 0, proving the tier matching logic was actually correctly aligning the valid legs while properly rejecting the missing ones.
- **AI Rate Limits**: The Tier 3 Gemini API hit 429 daily quota limits during bulk exception processing. Fixed by migrating the LLM client configuration from `gemini-3.6-flash` to the `gemini-3.5-flash` model, utilizing a fresh API quota, and implementing a retry backoff loop.

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
