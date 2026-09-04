import logging
import pandas as pd
from pathlib import Path
from recon.models import NormalizedRecord, RecordSource, TransactionType
from recon.sources.base import BaseSource
from recon.config import settings

logger = logging.getLogger(__name__)

class OMSSource(BaseSource):
    """OMS data source loader."""
    
    @property
    def source_name(self) -> str:
        return "OMS/ERP"
        
    def load(self) -> list[NormalizedRecord]:
        """Load and normalize records from OMS."""
        data_path = Path(settings.data_dir) / "oms_orders.csv"
        if not data_path.exists():
            raise FileNotFoundError(f"OMS data file not found: {data_path}")
            
        df = pd.read_csv(data_path)
        records = []
        
        for _, row in df.iterrows():
            if row.get("status") != "completed":
                continue
                
            amount = int(row.get("amount", 0))
            record = NormalizedRecord(
                source=RecordSource.OMS,
                record_id=str(row.get("order_ref")),
                transaction_type=TransactionType.PAYMENT,
                gross_amount=amount,
                net_amount=amount,
                timestamp=pd.to_datetime(row.get("created_at")),
                reference_ids={
                    "receipt": str(row.get("order_ref", "")),
                    "invoice_id": str(row.get("invoice_id", ""))
                },
                raw_data=row.to_dict()
            )
            records.append(record)
            
        logger.info(f"Loaded {len(records)} records from {self.source_name} source")
        return records
