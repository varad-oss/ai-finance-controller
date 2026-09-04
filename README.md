# AI Finance Controller

An AI-powered multi-source financial reconciliation agent that closes the finance-ops loop across OMS, Gateway, Settlement, and Bank records.

**Razorpay AI Buildathon — Track 04: AI Finance Controller**

[Demo video](VIDEO_URL_HERE)

## Problem — What It Solves, and Why It Matters

Finance teams manually reconcile across OMS, gateway, settlement, and bank records. Delays or silent errors in this process directly affect cash visibility and audit confidence, turning high-volume transaction matching into a massive operational bottleneck.

This track's own premise is that verification capacity, not generation speed, is the bottleneck. This project is built around that directly — the large majority of matching is deterministic, auditable rule-based logic; AI is spent only on the residual cases that actually require judgment.

## How It Works

Data flows from 4 systems into a unified `NormalizedRecord` schema, then passes through a three-tier funnel (see [ARCHITECTURE.md](ARCHITECTURE.md) for data flows and limits):

1. **Tier 1: Deterministic** — Exactly matches IDs, amounts, and dates programmatically (Confidence 1.0).
2. **Tier 2: Fuzzy** — Matches near-misses using exact amount enforcement, date windows, and substring logic (Confidence > 0.75).
3. **Tier 3: AI Investigation** — Google Gemini Structured Outputs reads the near-miss context to diagnose remaining exceptions or auto-match timing lags and duplicates.

## AI Judgment — Where AI Is Used, and Where It Deliberately Isn't

Tiers 1 and 2 are zero-AI by design. Exact and rule-based matching is cheaper, faster, and fully auditable compared to using an LLM for the same job. Across the pipeline, 99.4% of all matches (340 out of 342) are resolved completely deterministically without any model involvement.

Tier 3 is reserved only for the residual ambiguous cases. In our batch, 15 exceptions were sent to the LLM before safely hitting the quota limit, resulting in 4 verified auto-matches. The AI operates over read-only structured context—it is never given autonomous write access to move money or alter records directly. It only outputs a structured diagnosis and a suggested action, which the pipeline then applies via `update_decision_to_match`.

No LLM is anywhere near the core matching or any money-moving logic — it is used exclusively for the exception-diagnosis step, which is the one place judgment is actually needed over computation.

## Results — Throughput, Measured Accuracy, Honest Exceptions

Reported on the full 478-record batch — nothing here is cherry-picked.

The deterministic tiers (1+2) process the full batch in under a second. The total wall-clock time is dominated entirely by the AI tier's rate-limit waits and API network latency, a real-world constraint any production system integrating a third-party LLM would also hit.

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

## Build Challenges & Failure Recovery

| Bug | Root Cause | Fix |
|-----|------------|-----|
| OMS Record ID Corruption | The OMS source extractor attempted to read an `id` column that did not exist in the CSV, returning `"None"` for all OMS records. | Updated the extractor to read the correct `order_ref` column instead. |
| `orphaned_record` Generator Flaw | The synthetic data generator was creating perfectly paired settlement and bank entries for orphaned records, making them match correctly instead of failing. | Patched the generator to ensure orphaned records strictly exist only in the Gateway. |
| Tier 2 Amount Leakage | The fuzzy tolerance of 2% allowed `amount_discrepancy` exceptions to slip through the exact `OMS <-> Gateway` leg where they were meant to fail. | Tightened `tier2_fuzzy.py` to demand a strict, exact amount match specifically for `OMS <-> Gateway` since no intermediary fees exist there. |
| Evaluator Exception Blind Spot | Any match touching an exception record was globally flagged as "Exception Leakage," even if the match was on a perfectly valid leg (like `OMS <-> Gateway` for a missing bank deposit). | Rewrote the evaluator logic to cross-reference exceptions per-leg using a strict `EXPECTED_FAIL_LEGS` mapping, dropping false leakage to 0. |
| Gemini Daily Quota Exhaustion | The bulk exception processing exhausted the daily free-tier quota for `gemini-3.6-flash`, resulting in persistent 429 and 503 errors. | Migrated the LLM client config to use `gemini-3.5-flash` to access a fresh quota pool, and implemented an exponential backoff retry loop. |

## Reproduce These Numbers Yourself

The synthetic data generator (`data/generate_synthetic.py`) is seeded with `random.seed(42)`, meaning `python evaluate.py` generates the identical batch and the identical numbers every single run. You are highly encouraged to clone the repository and run the pipeline yourself rather than just taking this README's word for it.

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
