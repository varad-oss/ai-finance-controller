from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional

class RecordSource(str, Enum):
    OMS = "oms"
    GATEWAY = "gateway"
    RECON = "recon"
    BANK = "bank"

class TransactionType(str, Enum):
    PAYMENT = "payment"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"

class NormalizedRecord(BaseModel):
    """A transaction record normalized from any of the 4 sources."""
    source: RecordSource
    record_id: str               # Unique ID within this source
    transaction_type: TransactionType
    gross_amount: int            # In paise (always positive)
    net_amount: int              # In paise (gross - fee - tax for payments)
    fee: int = 0                 # In paise
    tax: int = 0                 # In paise
    currency: str = "INR"
    timestamp: datetime          # When the transaction occurred
    settlement_date: Optional[datetime] = None  # When it settled (if known)
    reference_ids: dict[str, str] = {}  # Cross-reference IDs (e.g., {"receipt": "ORD-2024-0001", "utr": "UTIB..."})
    description: str = ""
    raw_data: dict = {}          # Original source record for audit

class MatchResult(BaseModel):
    """Result of a matching decision between records."""
    left_source: RecordSource
    left_record_id: str
    right_source: RecordSource
    right_record_id: str
    match_tier: int              # 1, 2, or 3
    confidence: float            # 0.0-1.0
    rules_applied: list[str]     # Names of matching rules that contributed
    decision: str                # 'matched', 'human_review', 'unreconcilable'
    explanation: str = ""        # Human-readable reasoning

class ExceptionRecord(BaseModel):
    """An unmatched record flagged as an exception."""
    source: RecordSource
    record_id: str
    diagnosis_category: str      # e.g., 'timing_lag', 'fee_variance', etc.
    confidence: float
    explanation: str
    suggested_action: str        # 'manual_review', 'write_off', 'investigate'
    investigated_by: str = ""    # 'tier2_rules' or 'tier3_ai'
