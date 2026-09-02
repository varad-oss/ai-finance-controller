import json
import logging
import razorpay
from typing import Optional
from pathlib import Path

from recon.config import settings

logger = logging.getLogger(__name__)


class RazorpayClient:
    """Wrapper around the official razorpay SDK with a Mock Mode fallback."""
    
    def __init__(self, key_id: Optional[str] = None, key_secret: Optional[str] = None):
        self.key_id = key_id or settings.razorpay_key_id
        self.key_secret = key_secret or settings.razorpay_key_secret
        
        self.mock_mode = not (self.key_id and self.key_secret)
        
        if self.mock_mode:
            logger.warning("Razorpay API keys not provided. Running in MOCK MODE.")
        else:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def fetch_payments(self, from_time: int, to_time: int, count: int = 100) -> list[dict]:
        """Fetch captured payments within a time range."""
        if self.mock_mode:
            # Serve synthetic data
            data_path = settings.data_dir / "gateway_payments.json"
            if data_path.exists():
                with open(data_path, "r") as f:
                    return json.load(f)[:count]
            return []
            
        try:
            response = self.client.payment.all({
                "from": from_time,
                "to": to_time,
                "count": count
            })
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Failed to fetch payments: {e}")
            return []

    def fetch_settlements(self, count: int = 100) -> list[dict]:
        """Fetch settlements."""
        if self.mock_mode:
            return []
            
        try:
            response = self.client.settlement.all({"count": count})
            return response.get("items", [])
        except Exception as e:
            logger.error(f"Failed to fetch settlements: {e}")
            return []
