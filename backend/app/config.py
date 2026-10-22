import os
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./clincode.db")
SNOMED_SUBSET_PATH = Path(
    os.environ.get("SNOMED_SUBSET_PATH", Path(__file__).resolve().parents[2] / "data" / "snomed_subset.csv")
)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
REJECTION_RATE_ALERT_THRESHOLD = float(os.environ.get("REJECTION_RATE_ALERT_THRESHOLD", "0.4"))
