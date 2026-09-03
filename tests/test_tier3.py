import pytest
from unittest.mock import patch
from recon.models import NormalizedRecord, RecordSource, TransactionType, ExceptionRecord
from recon.matching.tier3_ai import investigate_exceptions
from datetime import datetime, timezone

@patch("recon.matching.tier3_ai.settings")
def test_tier3_fallback(mock_settings):
    """Test Tier 3 falls back gracefully if not configured."""
    mock_settings.llm_configured = False
    
    unmatched_by_source = {
        "oms": [
            NormalizedRecord(
                source=RecordSource.OMS,
                record_id="oms1",
                transaction_type=TransactionType.PAYMENT,
                gross_amount=1000,
                net_amount=1000,
                timestamp=datetime.now(timezone.utc)
            )
        ]
    }
    
    exceptions = investigate_exceptions(unmatched_by_source, db=None, batch_decision_ids=None)
    assert len(exceptions) == 1
    assert exceptions[0].diagnosis_category == "unreconcilable"
    assert "llm not configured" in exceptions[0].explanation.lower()
