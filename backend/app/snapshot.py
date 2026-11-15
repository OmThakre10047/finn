import json
from datetime import datetime

from . import db
from .config import PORTFOLIO, SNAPSHOT_DIR

SNAPSHOT_FILE = SNAPSHOT_DIR / "announcements_latest.json"
RESEARCH_FILE = SNAPSHOT_DIR / "research_reports.json"
RENDERS_FILE = SNAPSHOT_DIR / "renders.json"
ANNOUNCEMENTS_DB_FILE = SNAPSHOT_DIR / "announcements.json"
ALERTS_FILE = SNAPSHOT_DIR / "alerts.json"


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


def save_all() -> dict:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with db.get_db() as conn:
        research = conn.execute(
            "SELECT ticker, payload_json, generated_at, expires_at FROM research_reports WHERE status = 'done' AND payload_json IS NOT NULL"
        ).fetchall()
        renders = conn.execute(
            """SELECT r.kind, r.payload_json, a.ticker, a.headline, a.published_at
               FROM renders r JOIN announcements a ON a.id = r.announcement_id"""
        ).fetchall()
        announcements = conn.execute(
            """SELECT ticker, headline, nse_category, subject, category, materiality, priority, pdf_url,
                      published_at, summary, rules_handled, raw_json FROM announcements
               WHERE published_at >= datetime('now', '-35 days')"""
        ).fetchall()
        alerts = conn.execute(
            "SELECT ticker, type, payload_json, severity, dedupe_key, created_at FROM alerts ORDER BY created_at DESC"
        ).fetchall()
    research_out = [
        {"ticker": r["ticker"], "payload": json.loads(r["payload_json"]), "generated_at": r["generated_at"], "expires_at": r["expires_at"]}
        for r in research
    ]
    renders_out = [
        {"kind": r["kind"], "payload": json.loads(r["payload_json"]),
         "key": f"{r['ticker']}|{r['headline']}|{r['published_at']}"}
        for r in renders
    ]
    ann_out = [
        {"ticker": r["ticker"], "headline": r["headline"], "nse_category": r["nse_category"], "subject": r["subject"],
         "category": r["category"], "materiality": r["materiality"], "priority": r["priority"], "pdf_url": r["pdf_url"],
         "published_at": r["published_at"], "summary": r["summary"], "rules_handled": r["rules_handled"], "raw": json.loads(r["raw_json"] or "{}")}
        for r in announcements
    ]
    alerts_out = [
        {"ticker": r["ticker"], "type": r["type"], "payload": json.loads(r["payload_json"]), "severity": r["severity"], "dedupe_key": r["dedupe_key"], "created_at": r["created_at"]}
        for r in alerts
    ]
    RESEARCH_FILE.write_text(json.dumps(research_out, ensure_ascii=False))
    RENDERS_FILE.write_text(json.dumps(renders_out, ensure_ascii=False))
    ANNOUNCEMENTS_DB_FILE.write_text(json.dumps(ann_out, ensure_ascii=False))
    ALERTS_FILE.write_text(json.dumps(alerts_out, ensure_ascii=False))
    return {"research_reports": len(research_out), "renders": len(renders_out), "announcements": len(ann_out), "alerts": len(alerts_out)}


def restore_if_empty() -> dict:
    """Populate DB from committed snapshots on a fresh deploy (empty DB)."""
    restored = {"announcements": 0, "renders": 0, "research": 0, "alerts": 0}
    with db.get_db() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM announcements").fetchone()["c"]
    if n == 0:
        rows = []
        if ANNOUNCEMENTS_DB_FILE.exists():
            for r in json.loads(ANNOUNCEMENTS_DB_FILE.read_text()):
                rows.append({
                    "ticker": r["ticker"], "headline": r["headline"], "nse_category": r.get("nse_category"),
                    "subject": r.get("subject"), "pdf_url": r.get("pdf_url"), "published_at": r.get("published_at"),
                    "raw": r.get("raw", {}), "category": r.get("category"), "materiality": r.get("materiality"),
                    "priority": r.get("priority"), "summary": r.get("summary"), "rules_handled": r.get("rules_handled"),
                })
        if not rows:
            rows = load_snapshot()
        if rows:
            from .ingest import upsert_announcements

            with db.get_db() as conn:
                restored["announcements"] = upsert_announcements(conn, rows)
    if restored["announcements"] and RENDERS_FILE.exists():
        with db.get_db() as conn:
            id_by_key = {
                f"{r['ticker']}|{r['headline']}|{r['published_at']}": r["id"]
                for r in conn.execute("SELECT id, ticker, headline, published_at FROM announcements")
            }
            for item in json.loads(RENDERS_FILE.read_text()):
                aid = id_by_key.get(item["key"])
                if aid:
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, ?, ?)",
                        (aid, item["kind"], json.dumps(item["payload"], ensure_ascii=False)),
                    )
                    restored["renders"] += cur.rowcount
    if restored["announcements"] and RESEARCH_FILE.exists():
        with db.get_db() as conn:
            for item in json.loads(RESEARCH_FILE.read_text()):
                cur = conn.execute(
                    """INSERT OR IGNORE INTO research_reports (ticker, status, payload_json, generated_at, expires_at)
                       VALUES (?, 'done', ?, ?, ?)""",
                    (item["ticker"], json.dumps(item["payload"], ensure_ascii=False), item["generated_at"], item["expires_at"]),
                )
                restored["research"] += cur.rowcount
    if restored["announcements"] and ALERTS_FILE.exists():
        with db.get_db() as conn:
            for item in json.loads(ALERTS_FILE.read_text()):
                cur = conn.execute(
                    """INSERT OR IGNORE INTO alerts (ticker, type, payload_json, severity, dedupe_key, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (item["ticker"], item["type"], json.dumps(item["payload"], ensure_ascii=False),
                     item["severity"], item["dedupe_key"], item["created_at"]),
                )
                restored["alerts"] += cur.rowcount
    return restored
