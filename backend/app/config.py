import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
LLM_CHEAP = os.getenv("LLM_CHEAP", "")
LLM_STRONG = os.getenv("LLM_STRONG", "")

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
DB_PATH = (BACKEND_DIR / os.getenv("DB_PATH", "data/finn.db")).resolve()
SNAPSHOT_DIR = (BACKEND_DIR / os.getenv("SNAPSHOT_DIR", "data/snapshots")).resolve()
FORCE_SNAPSHOT = os.getenv("FORCE_SNAPSHOT", "0") == "1"

PORTFOLIO = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC", "TATAMOTORS", "MARUTI",
    "SUNPHARMA", "DRREDDY", "TITAN", "ADANIENT", "DLF", "TATAPOWER", "BEL",
    "PERSISTENT", "ASTRAL", "POLYCAB", "IRCTC",
]
ADHOC_TICKERS = ["ETERNAL", "DMART", "KPITTECH", "CDSL", "VARUNBEV"]

WATCH_TYPES = {
    "results": True,
    "mna": True,
    "fund_raise": True,
    "management_change": True,
    "litigation": True,
    "insider_trading": True,
    "earnings_call": False,
    "investor_meetings": False,
    "credit_rating": True,
    "dividend": False,
    "bonus_split": False,
    "capex": True,
    "press_release": False,
    "postal_ballot": False,
    "agm_egm": False,
    "pledging": True,
    "unclassified": False,
}

DEFAULT_ALERT_SETTINGS = {"volume_mult": 2.0, "price_move_pct": 4.0, "window_hours": 24}
