# AI Finance Controller

An AI-powered multi-source financial reconciliation agent that closes the finance-ops loop across OMS, Gateway, Settlement, and Bank records.

**Razorpay AI Buildathon — Track 04: AI Finance Controller**

[Demo video](VIDEO_URL_HERE)

## How It Works

Data flows from 4 systems into a unified `NormalizedRecord` schema, then passes through a three-tier funnel (see [ARCHITECTURE.md](ARCHITECTURE.md) for data flows and limits):

1. **Tier 1: Deterministic** — Exactly matches IDs, amounts, and dates programmatically (Confidence 1.0).
2. **Tier 2: Fuzzy** — Matches near-misses using exact amount enforcement, date windows, and substring logic (Confidence > 0.75).
3. **Tier 3: AI Investigation** — Google Gemini Structured Outputs reads the near-miss context to diagnose remaining exceptions or auto-match timing lags and duplicates.

## Results

| Metric | Value |
|--------|-------|
| Processing Time | 163,217 ms |
| Total Records Ingested | 478 |
| Verified Correct Matches | 300 |
| Total Matches Made | 342 |
| Unverified Matches | 42 |
| Exceptions Flagged | 36 |
| False Matches (wrong pair) | 0 |
| Exception Leakage | 0 |
| Tier 1 Exact Matches | 339 |
| Tier 2 Fuzzy Matches | 1 |
| Tier 3 AI Matches | 4 |

## Known Limitations

- **Free-Tier API Quota:** Tier 3 AI processed 15 API calls before safely halting due to our configured `TIER3_MAX_LLM_CALLS` safety limit, flagging the remaining 36 exceptions for human review without AI.
- **Dispute Adjustments Uncatchable:** The synthetic `dispute_adjustment` records are intentionally generated identically to normal ones, meaning the system currently reconciles them normally without flagging them as disputes.
- **Unverified Matches (42):** These are valid sub-legs (e.g., `Gateway <-> Recon`) belonging to exception records that the ground-truth evaluator doesn't explicitly label as "correct," meaning they are technically unverified by the test suite, but correctly matched by the engine.

## Setup & Run

1. **Install dependencies**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

2. **Configure environment**
```bash
cp .env.example .env
```
Add your **Razorpay Test Keys** (`RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`) and your **Gemini API Key** (`GEMINI_API_KEY`) to `.env`.

3. **Run the pipeline**
```bash
python evaluate.py
```
The detailed HTML report generates at `results/report.html` and the full CLI evaluation outputs to the terminal.

## Project Structure
- `src/recon/` - Core engine (tiers, models, db config)
- `data/` - Synthetic data generator and JSON/CSV outputs
- `results/` - HTML report, JSON metrics, and run logs
- `tests/` - Pytest suite

## License
MIT License - See [LICENSE](LICENSE) for details.
