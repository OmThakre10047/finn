import json
from datetime import datetime

from . import nse_client
from .config import PORTFOLIO, SNAPSHOT_DIR
from .db import get_db, set_source_state

SNAPSHOT_FILE = SNAPSHOT_DIR / "announcements_latest.json"


def save_snapshot(rows: list[dict]) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    portfolio = set(PORTFOLIO)
    ours = [r for r in rows if r["ticker"] in portfolio]
    payload = {"fetched_at": datetime.now().isoformat(timespec="seconds"), "count": len(ours), "rows": ours}
    SNAPSHOT_FILE.write_text(json.dumps(payload, ensure_ascii=False))


def load_snapshot() -> list[dict]:
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text())["rows"]
    return []


def upsert_announcements(conn, rows: list[dict], rules_handled: int = 0) -> int:
    n = 0
    for r in rows:
        cur = conn.execute(
            """INSERT OR IGNORE INTO announcements
               (ticker, headline, nse_category, subject, pdf_url, published_at, raw_json,
                category, materiality, priority, summary, rules_handled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r["ticker"], r["headline"], r["nse_category"], r["subject"], r["pdf_url"],
             r["published_at"], json.dumps(r["raw"], ensure_ascii=False),
             r.get("category"), r.get("materiality"),
             r.get("priority", 0) if r.get("priority") is not None else 0,
             r.get("summary"),
             r.get("rules_handled", 0) if r.get("rules_handled") is not None else rules_handled),
        )
        n += cur.rowcount
    return n


def ingest(days_back: int = 3) -> dict:
    result = {"mode": "snapshot", "fetched": 0, "inserted": 0, "error": None, "strategy": None}
    try:
        rows, strategy = nse_client.fetch_with_meta(days_back)
        result.update(mode="live", fetched=len(rows), strategy=strategy)
        save_snapshot(rows)
        set_source_state("nse_announcements", "live")
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        rows = load_snapshot()
        result["fetched"] = len(rows)
        set_source_state("nse_announcements", "snapshot", result["error"])
    portfolio = set(PORTFOLIO)
    ours = [r for r in rows if r["ticker"] in portfolio]
    with get_db() as conn:
        result["inserted"] = upsert_announcements(conn, ours)
    return result
