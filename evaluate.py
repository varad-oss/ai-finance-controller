"""Evaluation harness.

Runs the reconciliation pipeline and evaluates the output against
the ground truth synthetic data. Computes honest metrics (match rate,
false match rate, AI marginal value).
"""

import json
import logging
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

from recon.audit.db import AuditDB
from recon.matching.pipeline import ReconciliationPipeline
from recon.reporting.html_report import generate_html_report
from recon.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
console = Console()


def load_ground_truth() -> dict:
    gt_path = settings.data_dir / "ground_truth.json"
    if not gt_path.exists():
        logger.error(f"Ground truth file not found at {gt_path}")
        sys.exit(1)
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_gt_lookup(gt: dict) -> dict:
    """Builds a lookup of valid match pairs from ground truth."""
    # Maps record_id -> set of acceptable match IDs
    # Since our pipeline matches pairs across sources (e.g., OMS->GW, GW->Recon, Recon->Bank)
    lookup = {}
    
    for row in gt.get("matches", []):
        oms = row.get("oms_order_ref")
        gw = row.get("gateway_payment_id")
        recon = row.get("recon_entity_id")
        bank = row.get("bank_utr")
        
        # If it's a refund, the gateway record id is actually the recon_entity_id
        if recon and recon.startswith("rfnd_"):
            gw = recon
            
        # Gateway <-> OMS
        if oms and gw:
            lookup.setdefault(oms, set()).add(gw)
            lookup.setdefault(gw, set()).add(oms)
        
        # Recon <-> Gateway
        if recon and gw:
            lookup.setdefault(recon, set()).add(gw)
            lookup.setdefault(gw, set()).add(recon)
            
        # Recon <-> Bank
        if recon and bank:
            lookup.setdefault(recon, set()).add(bank)
            lookup.setdefault(bank, set()).add(recon)

    return lookup


def evaluate(batch_id: str, db: AuditDB):
    gt = load_ground_truth()
    gt_matches_lookup = build_gt_lookup(gt)

    decisions = db.get_decisions_for_batch(batch_id)
    
    # Analyze decisions
    total_decisions = len(decisions)
    matches_made = [d for d in decisions if d["decision"] == "matched"]
    exceptions_flagged = [d for d in decisions if d["decision"] != "matched"]

    correct_matches = 0
    false_matches = 0
    unverified = 0
    
    exception_report = []

    for m in matches_made:
        left_id = m["record_id"]
        right_id = m["matched_record_id"]
        
        acceptable_matches = gt_matches_lookup.get(left_id, set())
        
        if left_id in gt_matches_lookup:
            if right_id in acceptable_matches:
                correct_matches += 1
            else:
                false_matches += 1
                exception_report.append({
                    "left_id": left_id,
                    "wrong_right_id": right_id,
                    "correct_right_ids": list(acceptable_matches)
                })
        else:
            unverified += 1

    summary = db.get_batch_summary(batch_id)
    
    # Print rich table
    console.print("\n[bold blue]=== Reconciliation Evaluation Results ===[/bold blue]\n")
    
    if not settings.llm_configured:
        console.print("[bold red blink]WARNING: Tier 3 AI Investigation was SKIPPED because no LLM API key was configured.[/bold red blink]\n")
    
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    
    t.add_row("Total Records Ingested", str(summary["total_records"]))
    t.add_row("Tier 1 Exact Matches", str(summary["tier1_matched"]))
    t.add_row("Tier 2 Fuzzy Matches", str(summary["tier2_matched"]))
    t.add_row("Tier 3 AI Matches", str(summary["tier3_matched"]))
    t.add_row("Total Matches Made", str(len(matches_made)))
    t.add_row("Verified Correct Matches", str(correct_matches))
    t.add_row("False Matches", f"[red]{false_matches}[/red]" if false_matches > 0 else "[green]0[/green]")
    t.add_row("Unverified Matches", str(unverified))
    t.add_row("Exceptions Flagged (Human Review)", str(len(exceptions_flagged)))
    t.add_row("Processing Time (ms)", str(summary["processing_time_ms"]))

    console.print(t)
    
    console.print("\n[bold green]Success![/bold green] Results evaluated against ground truth.")
    
    # Save results
    settings.results_dir.mkdir(exist_ok=True)
    with open(settings.results_dir / "metrics.json", "w") as f:
        json.dump({
            "batch_id": batch_id,
            "total_records": summary["total_records"],
            "matches_made": len(matches_made),
            "correct_matches": correct_matches,
            "false_matches": false_matches,
            "unverified_matches": unverified,
            "tier1_matched": summary["tier1_matched"],
            "tier2_matched": summary["tier2_matched"],
            "tier3_matched": summary["tier3_matched"],
            "processing_time_ms": summary["processing_time_ms"],
        }, f, indent=2)

    with open(settings.results_dir / "exception_report.json", "w") as f:
        json.dump(exception_report, f, indent=2)


if __name__ == "__main__":
    db = AuditDB()
    db.initialize()
    pipeline = ReconciliationPipeline(db)
    
    console.print("[bold yellow]Running Reconciliation Pipeline...[/bold yellow]")
    batch_id = pipeline.run()
    
    console.print(f"Pipeline finished. Batch ID: {batch_id}")
    evaluate(batch_id, db)
    
    generate_html_report(batch_id, db, output_path="results/report.html")
    console.print("View the detailed HTML report at [bold cyan]results/report.html[/bold cyan]")

