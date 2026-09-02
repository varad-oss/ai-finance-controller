import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from recon.models import NormalizedRecord, RecordSource, TransactionType
from recon.sources.base import BaseSource
from recon.config import settings

logger = logging.getLogger(__name__)

class SettlementSource(BaseSource):
    """Settlement data source loader."""
    
    @property
    def source_name(self) -> str:
        return "Settlement Recon"
        
    def load(self) -> list[NormalizedRecord]:
        """Load and normalize records from Settlement Recon."""
        data_path = Path(settings.data_dir) / "settlement_recon.json"
        if not data_path.exists():
            raise FileNotFoundError(f"Settlement recon data file not found: {data_path}")
            
        with open(data_path, 'r') as f:
            data = json.load(f)
            
        records = []
        for item in data:
            item_type = item.get("type", "payment")
            gross_amount = int(item.get("amount", 0))
            
            if item_type == "payment":
                net_amount = int(item.get("credit", 0))
                fee = int(item.get("fee", 0))
                tax = int(item.get("tax", 0))
                txn_type = TransactionType.PAYMENT
            else:
                net_amount = int(item.get("debit", 0))
                fee = 0
                tax = 0
                txn_type = TransactionType.REFUND
                
            record = NormalizedRecord(
                source=RecordSource.RECON,
                record_id=str(item.get("entity_id")),
                transaction_type=txn_type,
                gross_amount=gross_amount,
                net_amount=net_amount,
                fee=fee,
                tax=tax,
                timestamp=datetime.fromtimestamp(item.get("created_at", 0), tz=timezone.utc),
                settlement_date=datetime.fromtimestamp(item.get("settled_at", 0), tz=timezone.utc) if item.get("settled_at") else None,
                reference_ids={
                    "settlement_id": str(item.get("settlement_id", "")),
                    "utr": str(item.get("utr", ""))
                },
                raw_data=item
            )
            records.append(record)
            
        logger.info(f"Loaded {len(records)} records from {self.source_name} source")
        return records
