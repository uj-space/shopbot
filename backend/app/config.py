"""Environment and runtime settings for ShopBot."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "claude-haiku-5-5").strip() or "claude-haiku-5-5"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "shopbot_local.db")).strip()
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

MAX_SHORT_TERM_MESSAGES = int(os.getenv("MAX_SHORT_TERM_MESSAGES", "8"))
FREE_SHIPPING_THRESHOLD_PKR = 6000
FLAT_SHIPPING_PKR = 250
STORE_NAME = "Khaas Studio"
