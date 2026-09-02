import pytest
from datetime import datetime

from recon.models import NormalizedRecord, RecordSource, TransactionType
from recon.matching.tier1_exact import match_oms_to_gateway

def test_tier1_exact_match():
    # Arrange
    oms_record = NormalizedRecord(
        source=RecordSource.OMS,
        record_id="oms-1",
        transaction_type=TransactionType.PAYMENT,
        gross_amount=10000,
        net_amount=10000,
        timestamp=datetime.now(),
        reference_ids={"receipt": "ORD-001"}
    )
    
    gw_record = NormalizedRecord(
        source=RecordSource.GATEWAY,
        record_id="pay_1",
        transaction_type=TransactionType.PAYMENT,
        gross_amount=10000,
        net_amount=9800,
        fee=200,
        timestamp=datetime.now(),
        reference_ids={"receipt": "ORD-001"}
    )
    
    # Act
    matches, unmatched_oms, unmatched_gw = match_oms_to_gateway([oms_record], [gw_record])
    
    # Assert
    assert len(matches) == 1
    assert matches[0].confidence == 1.0
    assert matches[0].match_tier == 1
    assert matches[0].left_record_id == "oms-1"
    assert matches[0].right_record_id == "pay_1"
    assert len(unmatched_oms) == 0
    assert len(unmatched_gw) == 0

def test_tier1_mismatch_amount():
    # Arrange
    oms_record = NormalizedRecord(
        source=RecordSource.OMS,
        record_id="oms-1",
        transaction_type=TransactionType.PAYMENT,
        gross_amount=10000,
        net_amount=10000,
        timestamp=datetime.now(),
        reference_ids={"receipt": "ORD-001"}
    )
    
    gw_record = NormalizedRecord(
        source=RecordSource.GATEWAY,
        record_id="pay_1",
        transaction_type=TransactionType.PAYMENT,
        gross_amount=10100, # different amount
        net_amount=9900,
        timestamp=datetime.now(),
        reference_ids={"receipt": "ORD-001"}
    )
    
    # Act
    matches, unmatched_oms, unmatched_gw = match_oms_to_gateway([oms_record], [gw_record])
    
    # Assert
    assert len(matches) == 0
    assert len(unmatched_oms) == 1
    assert len(unmatched_gw) == 1
