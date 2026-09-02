import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from recon.models import NormalizedRecord, RecordSource, TransactionType
from recon.sources.base import BaseSource
from recon.config import settings

logger = logging.getLogger(__name__)

class GatewaySource(BaseSource):
    """Gateway data source loader."""
    
    @property
    def source_name(self) -> str:
        return "Razorpay Gateway"
        
    def load(self) -> list[NormalizedRecord]:
        """Load and normalize records from Gateway."""
        payments_path = Path(settings.data_dir) / "gateway_payments.json"
        refunds_path = Path(settings.data_dir) / "gateway_refunds.json"
        
        records = []
        
        if payments_path.exists():
            with open(payments_path, 'r') as f:
                payments_data = json.load(f)
                
            for p in payments_data:
                if p.get("status") != "captured":
                    continue
                    
                gross_amount = int(p.get("amount", 0))
                fee = int(p.get("fee", 0))
                tax = int(p.get("tax", 0))
                net_amount = gross_amount - fee - tax
                
                records.append(NormalizedRecord(
                    source=RecordSource.GATEWAY,
                    record_id=str(p.get("id")),
                    transaction_type=TransactionType.PAYMENT,
                    gross_amount=gross_amount,
                    net_amount=net_amount,
                    fee=fee,
                    tax=tax,
                    timestamp=datetime.fromtimestamp(p.get("created_at", 0), tz=timezone.utc),
                    reference_ids={
                        "receipt": str(p.get("receipt", "")),
                        "order_id": str(p.get("order_id", ""))
                    },
                    raw_data=p
                ))
        else:
            logger.warning(f"Gateway payments file not found: {payments_path}")
            
        if refunds_path.exists():
            with open(refunds_path, 'r') as f:
                refunds_data = json.load(f)
                
            for r in refunds_data:
                amount = int(r.get("amount", 0))
                
                records.append(NormalizedRecord(
                    source=RecordSource.GATEWAY,
                    record_id=str(r.get("id")),
                    transaction_type=TransactionType.REFUND,
                    gross_amount=amount,
                    net_amount=amount,
                    timestamp=datetime.fromtimestamp(r.get("created_at", 0), tz=timezone.utc),
                    reference_ids={
                        "receipt": str(r.get("receipt", "")),
                        "payment_id": str(r.get("payment_id", ""))
                    },
                    raw_data=r
                ))
        else:
            logger.warning(f"Gateway refunds file not found: {refunds_path}")
            
        if not payments_path.exists() and not refunds_path.exists():
            raise FileNotFoundError("Neither gateway payments nor refunds file found.")
            
        logger.info(f"Loaded {len(records)} records from {self.source_name} source")
        return records
