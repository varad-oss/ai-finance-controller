"""CLI Report generator for reconciliation results."""

import logging
from rich.console import Console
from rich.table import Table

from recon.audit.db import AuditDB
from recon.config import settings

logger = logging.getLogger(__name__)
console = Console()

def generate_cli_report(batch_id: str, db: AuditDB):
    """Generate a rich CLI report for a reconciliation batch."""
    summary = db.get_batch_summary(batch_id)
    if not summary:
        logger.error(f"No summary found for batch {batch_id}")
        return

    console.print("\n[bold blue]=== Reconciliation Batch Report ===[/bold blue]\n")
    
    if not settings.llm_configured:
        console.print("[bold red blink]WARNING: Tier 3 AI Investigation was SKIPPED because no LLM API key was configured.[/bold red blink]\n")
    
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("Metric")
    t.add_column("Value", justify="right")
    
    t.add_row("Batch ID", summary["id"])
    t.add_row("Total Records Ingested", str(summary["total_records"]))
    t.add_row("Tier 1 Exact Matches", str(summary["tier1_matched"]))
    t.add_row("Tier 2 Fuzzy Matches", str(summary["tier2_matched"]))
    t.add_row("Tier 3 AI Matches", str(summary["tier3_matched"]))
    t.add_row("Total Matches Made", str(summary["tier1_matched"] + summary["tier2_matched"] + summary["tier3_matched"]))
    t.add_row("Flagged for Human Review", str(summary["human_review"]))
    t.add_row("Processing Time (ms)", str(summary["processing_time_ms"]))

    console.print(t)

    decisions = db.get_decisions_for_batch(batch_id)
    human_review = [d for d in decisions if d["decision"] != "matched"]
    
    if human_review:
        console.print("\n[bold red]Exceptions (Flagged for Review):[/bold red]")
        exception_table = Table(show_header=True, header_style="bold red")
        exception_table.add_column("Source", style="dim")
        exception_table.add_column("Record ID")
        exception_table.add_column("Diagnosis / Reason")
        
        for hr in human_review:
            # check if AI investigated
            ai_data = db.get_ai_investigation(hr["id"])
            if ai_data:
                reason = f"{ai_data['diagnosis_category']}: {ai_data['explanation']}"
            else:
                reason = hr["explanation"] or "Failed Tier 1 & Tier 2"
            exception_table.add_row(hr["record_source"], hr["record_id"], reason)
            
        console.print(exception_table)
