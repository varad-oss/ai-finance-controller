import logging
import pandas as pd
from pathlib import Path
from recon.models import NormalizedRecord, RecordSource, TransactionType
from recon.sources.base import BaseSource
from recon.config import settings

logger = logging.getLogger(__name__)

class BankSource(BaseSource):
    """Bank statement data source loader."""
    
    @property
    def source_name(self) -> str:
        return "Bank Statement"
        
    def load(self) -> list[NormalizedRecord]:
        """Load and normalize records from Bank Statement."""
        data_path = Path(settings.data_dir) / "bank_statement.csv"
        if not data_path.exists():
            raise FileNotFoundError(f"Bank statement file not found: {data_path}")
            
        df = pd.read_csv(data_path)
        records = []
        
        for idx, row in df.iterrows():
            credit = float(row.get("credit", 0)) if pd.notna(row.get("credit")) else 0
            debit = float(row.get("debit", 0)) if pd.notna(row.get("debit")) else 0
            
            if credit == 0 and debit == 0:
                continue
                
            if credit > 0:
                gross_amount = int(round(credit * 100))
                txn_type = TransactionType.PAYMENT
            else:
                gross_amount = int(round(debit * 100))
                txn_type = TransactionType.REFUND
                
            ref_str = str(row.get("reference", ""))
            desc_str = str(row.get("description", ""))
            
            # Simple UTR extraction logic (can be improved)
            utr = ""
            if len(ref_str) > 5 and ref_str != "nan":
                utr = ref_str
            elif len(desc_str) > 10 and desc_str != "nan":
                # Very basic heuristic for UTR
                words = desc_str.split()
                for word in words:
                    if len(word) > 10 and word.isalnum():
                        utr = word
                        break
                        
            record = NormalizedRecord(
                source=RecordSource.BANK,
                record_id=f"bank_{idx}",
                transaction_type=txn_type,
                gross_amount=gross_amount,
                net_amount=gross_amount,
                timestamp=pd.to_datetime(row.get("date"), format="%d/%m/%Y"),
                reference_ids={"utr": utr} if utr else {},
                description=desc_str,
                raw_data=row.to_dict()
            )
            records.append(record)
            
        logger.info(f"Loaded {len(records)} records from {self.source_name} source")
        return records
