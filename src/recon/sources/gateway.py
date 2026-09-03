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
        records = []
        payments_data = []
        refunds_data = []
        
        # Always load synthetic data for the baseline
        payments_path = Path(settings.data_dir) / "gateway_payments.json"
        refunds_path = Path(settings.data_dir) / "gateway_refunds.json"
        
        if payments_path.exists():
            with open(payments_path, 'r') as f:
                payments_data.extend(json.load(f))
        if refunds_path.exists():
            with open(refunds_path, 'r') as f:
                refunds_data.extend(json.load(f))
        
        try:
            from recon.razorpay_client.client import RazorpayClient
            client = RazorpayClient()
            if not client.mock_mode:
                logger.info("GatewaySource fetching from REAL Razorpay API to combine with synthetic data (Hybrid Mode).")
                import time
                now = int(time.time())
                from_time = now - (90 * 24 * 60 * 60) # 90 days ago
                live_payments = client.fetch_payments(from_time=from_time, to_time=now, count=100)
                payments_data.extend(live_payments)
        except Exception as e:
            logger.error(f"Error fetching real gateway data: {e}")

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
            
        logger.info(f"Loaded {len(records)} records from {self.source_name} source")
        return records
