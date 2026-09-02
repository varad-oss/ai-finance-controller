"""Main entry point for the reconciliation agent."""

import sys
import logging
from rich.console import Console

from recon.audit.db import AuditDB
from recon.matching.pipeline import ReconciliationPipeline
from recon.reporting.cli_report import generate_cli_report
from recon.reporting.html_report import generate_html_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
console = Console()

def main():
    console.print("[bold blue]AI Finance Controller - Reconciliation Agent[/bold blue]")
    
    try:
        db = AuditDB()
        db.initialize()
        
        pipeline = ReconciliationPipeline(db)
        batch_id = pipeline.run()
        
        generate_cli_report(batch_id, db)
        generate_html_report(batch_id, db, output_path="results/report.html")
        
        console.print(f"\n[bold green]Reconciliation complete![/bold green] Batch ID: {batch_id}")
        console.print("Run `python evaluate.py` to see metrics and evaluation against ground truth.")
        console.print("View the detailed HTML report at [bold cyan]results/report.html[/bold cyan]")
        
    except Exception as e:
        logger.exception("Pipeline failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
