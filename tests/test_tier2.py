from datetime import datetime, timezone, timedelta
from recon.models import NormalizedRecord, RecordSource, TransactionType
from recon.matching.tier2_fuzzy import match_oms_to_gateway_fuzzy

def test_tier2_fuzzy_amount_and_date():
    """Test fuzzy matching handles slight date shifts and amount variations."""
    now = datetime.now(timezone.utc)
    
    oms = [
        NormalizedRecord(
            source=RecordSource.OMS,
            record_id="oms1",
            transaction_type=TransactionType.PAYMENT,
            gross_amount=1000,
            net_amount=1000,
            timestamp=now,
            reference_ids={"receipt": "rec123"}
        )
    ]
    
    # Gateway amount must be exact for OMS-Gateway, date off by 1 day
    gw = [
        NormalizedRecord(
            source=RecordSource.GATEWAY,
            record_id="gw1",
            transaction_type=TransactionType.PAYMENT,
            gross_amount=1000,
            net_amount=980,
            timestamp=now + timedelta(days=1),
            reference_ids={"receipt": "rec123_gw"}
        )
    ]
    
    matches, un_oms, un_gw = match_oms_to_gateway_fuzzy(oms, gw)
    assert len(matches) == 1
    assert matches[0].confidence > 0.75
    assert len(un_oms) == 0
