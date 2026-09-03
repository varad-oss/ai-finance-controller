"""Application configuration using Pydantic Settings.

Reads from .env file and environment variables. All thresholds are tunable
without code changes — just edit .env.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is three levels up from this file: src/recon/config.py → project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Central configuration for the reconciliation agent."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Razorpay API ---
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # --- LLM (Tier 3 AI Investigation) ---
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.6-flash"
    
    # --- Matching Thresholds ---
    tier2_confidence_threshold: float = 0.75
    tier3_confidence_threshold: float = 0.80
    tier2_amount_tolerance_percent: float = 2.0
    tier2_date_window_days: int = 3
    tier3_max_llm_calls: int = 50

    # --- Paths ---
    data_dir: Path = PROJECT_ROOT / "data" / "synthetic"
    results_dir: Path = PROJECT_ROOT / "results"
    audit_db_path: Path = PROJECT_ROOT / "audit_trail.db"

    @property
    def razorpay_configured(self) -> bool:
        """Check if Razorpay API keys are provided."""
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def llm_configured(self) -> bool:
        """Check if Gemini API key is provided."""
        return bool(self.gemini_api_key)


# Singleton instance — import this wherever config is needed
settings = Settings()
