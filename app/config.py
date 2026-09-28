"""Settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = os.getenv("DB_PATH", str(ROOT / "data" / "flamingo.db"))
SOURCES_FILE = os.getenv("SOURCES_FILE", str(ROOT / "sources.yaml"))
TIMELINE_FILE = os.getenv("TIMELINE_FILE", str(ROOT / "timeline.yaml"))
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000").rstrip("/")
FETCH_INTERVAL_MINUTES = int(os.getenv("FETCH_INTERVAL_MINUTES", "10"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")
AI_MODE = os.getenv("AI_MODE", "real")  # "real", "fake" or "off"
AI_MONTHLY_BUDGET_USD = float(os.getenv("AI_MONTHLY_BUDGET_USD", "10"))

USER_AGENT = f"FlamingoWatchBot/1.0 (+{SITE_URL}/about)"

# Haiku 4.5 list prices, USD per million tokens (checked 2026-09-28).
AI_PRICE_INPUT_PER_M = float(os.getenv("AI_PRICE_INPUT_PER_M", "1.0"))
AI_PRICE_OUTPUT_PER_M = float(os.getenv("AI_PRICE_OUTPUT_PER_M", "5.0"))
AI_MAX_PER_RUN = int(os.getenv("AI_MAX_PER_RUN", "40"))
# When AI works again, summarise headline-only articles from this many recent days.
AI_CATCHUP_DAYS = int(os.getenv("AI_CATCHUP_DAYS", "3"))
RUN_SCHEDULER = os.getenv("RUN_SCHEDULER", "1") == "1"
# Protest day counter in the hero. 31 May 2026 = start of the daily protests in Tirana
# (Wikipedia); checked against reported day 80 (18 Aug), day 100 (7 Sep), day 121 (28 Sep).
# Set PROTEST_START empty to hide the counter.
PROTEST_START = os.getenv("PROTEST_START", "2026-05-31")
# Pages of older stories exported for browsers without JavaScript (/page/2 ... /page/N).
MAX_FEED_PAGES = 10

# Static-site mode: when EXPORT_DIR is set, every pipeline run also writes a
# complete static copy of the site there, for publishing to free static hosting.
EXPORT_DIR = os.getenv("EXPORT_DIR", "")
