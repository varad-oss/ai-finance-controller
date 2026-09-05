"""Pipeline Orchestrator.

Runs Data Ingestion -> Tier 1 -> Tier 2 -> Tier 3 -> Reporting.
Logs everything to the Audit Database.
"""

import logging
import time

from recon.sources.oms import OMSSource
from recon.sources.gateway import GatewaySource
from recon.sources.settlement import SettlementSource
from recon.sources.bank import BankSource
from recon.matching.tier1_exact import run_tier1
from recon.matching.tier2_fuzzy import run_tier2
from recon.matching.tier3_ai import investigate_exceptions
from recon.audit.db import AuditDB
from recon.config import settings

logger = logging.getLogger(__name__)


class ReconciliationPipeline:
    def __init__(self, db: AuditDB):
        self.db = db

    def run(self) -> str:
        """Run the full reconciliation pipeline and return the batch ID."""
        start_time = time.time()
        
        # 1. Start Batch
        config_snapshot = {
            "tier2_confidence_threshold": settings.tier2_confidence_threshold,
            "tier3_confidence_threshold": settings.tier3_confidence_threshold,
            "tier2_amount_tolerance_percent": settings.tier2_amount_tolerance_percent,
            "tier2_date_window_days": settings.tier2_date_window_days,
        }
        batch_id = self.db.start_batch(config_snapshot)
        logger.info("Started batch %s", batch_id)

        # 2. Ingest Data
        try:
            from recon.razorpay_client.client import RazorpayClient
            rzp_client = RazorpayClient()
            if not rzp_client.mock_mode:
                logger.info("Executing real Razorpay API write (creating test order) for demonstration.")
                # Create a sample order to prove write access
                rzp_client.create_order(amount=50000, receipt=f"demo_receipt_{batch_id[:6]}")
        except Exception as e:
            logger.warning(f"Failed to create demo order: {e}")

        oms_loader = OMSSource()
        gw_loader = GatewaySource()
        setl_loader = SettlementSource()
        bank_loader = BankSource()

        oms_records = oms_loader.load()
        gw_records = gw_loader.load()
        setl_records = setl_loader.load()
        bank_records = bank_loader.load()

        total_records = len(oms_records) + len(gw_records) + len(setl_records) + len(bank_records)
        logger.info("Ingested %d total records", total_records)

        # 3. Tier 1: Deterministic
        t1_result = run_tier1(oms_records, gw_records, setl_records, bank_records)
        tier1_matched = len(t1_result.matches)
        
        for match in t1_result.matches:
            self.db.log_match(
                batch_id=batch_id,
                record_source=match.left_source.value,
                record_id=match.left_record_id,
                matched_source=match.right_source.value,
                matched_record_id=match.right_record_id,
                match_tier=match.match_tier,
                confidence=match.confidence,
                rules_applied=match.rules_applied,
                decision=match.decision,
                explanation=match.explanation,
            )

        # 4. Tier 2: Fuzzy
        t2_result = run_tier2(
            t1_result.unmatched_by_source["oms"],
            t1_result.unmatched_by_source["gateway"],
            t1_result.unmatched_by_source["recon"],
            t1_result.unmatched_by_source["bank"],
        )
        tier2_matched = len(t2_result.matches)

        for match in t2_result.matches:
            self.db.log_match(
                batch_id=batch_id,
                record_source=match.left_source.value,
                record_id=match.left_record_id,
                matched_source=match.right_source.value,
                matched_record_id=match.right_record_id,
                match_tier=match.match_tier,
                confidence=match.confidence,
                rules_applied=match.rules_applied,
                decision=match.decision,
                explanation=match.explanation,
            )

        # 5. Log Unmatched & prepare for Tier 3
        # We log unmatched records to DB with decision 'human_review' (which might be upgraded to 'matched' by AI, but for now we log them as unmatched)
        batch_decision_ids = {}
        for source, records in t2_result.unmatched_by_source.items():
            for r in records:
                did = self.db.log_match(
                    batch_id=batch_id,
                    record_source=source,
                    record_id=r.record_id,
                    matched_source=None,
                    matched_record_id=None,
                    match_tier=None,
                    confidence=0.0,
                    rules_applied=[],
                    decision="unreconcilable",
                    explanation="Failed Tier 1 and Tier 2 matching."
                )
                batch_decision_ids[r.record_id] = did

        # 6. Tier 3: AI Exception Investigation
        exceptions = investigate_exceptions(
            unmatched_by_source=t2_result.unmatched_by_source,
            db=self.db,
            batch_decision_ids=batch_decision_ids
        )

        # Apply Tier 3 AI matches to the DB
        updated_decisions = set()
        for e in exceptions:
            if e.suggested_action == "auto_match" and e.suggested_match_id:
                # Find the matched source based on context
                decision_id = batch_decision_ids.get(e.record_id)
                if decision_id and decision_id not in updated_decisions:
                    self.db.update_decision_to_match(
                        decision_id=decision_id,
                        matched_source="AI_SUGGESTED", # Or we could derive it if we had it
                        matched_record_id=e.suggested_match_id,
                        match_tier=3,
                        confidence=e.confidence,
                        explanation=e.explanation
                    )
                    updated_decisions.add(decision_id)

        tier3_matched = len(updated_decisions)
        human_review = sum(1 for e in exceptions if e.suggested_action != "auto_match")

        # 7. Complete Batch
        processing_time = int((time.time() - start_time) * 1000)
        self.db.complete_batch(
            batch_id=batch_id,
            total_records=total_records,
            tier1_matched=tier1_matched,
            tier2_matched=tier2_matched,
            tier3_matched=tier3_matched,
            human_review=human_review,
            unreconcilable=0, # Captured in human_review
            processing_time_ms=processing_time,
            false_matches=0 # Evaluated externally
        )

        logger.info("Pipeline complete in %d ms. Batch: %s", processing_time, batch_id)
        return batch_id
