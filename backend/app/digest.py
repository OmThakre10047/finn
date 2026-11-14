from datetime import datetime, timedelta
import json

from . import db
from .config import PORTFOLIO


def _parse_pub(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d %b %Y %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def build_digest(window_hours: int = 24, ticker: str | None = None) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)
    with db.get_db() as conn:
        rows = conn.execute(
            """SELECT id, ticker, headline, subject, category, materiality, priority, pdf_url,
                      published_at, summary, rules_handled
               FROM announcements ORDER BY priority DESC, id DESC LIMIT 2000"""
        ).fetchall()
        watch = {r["key"]: bool(r["is_enabled"]) for r in conn.execute("SELECT key, is_enabled FROM watch_types")}
        renders = {}
        for r in conn.execute("SELECT announcement_id, kind, payload_json FROM renders"):
            try:
                renders.setdefault(r["announcement_id"], {})[r["kind"]] = json.loads(r["payload_json"])
            except (TypeError, ValueError):
                pass

    material, routine = [], []
    seen = set()
    for r in rows:
        pub = _parse_pub(r["published_at"])
        if pub and pub < cutoff:
            continue
        if r["ticker"] not in PORTFOLIO or r["id"] in seen:
            continue
        seen.add(r["id"])
        item = {
            **dict(r),
            "watched": watch.get(r["category"], False),
            "renders": renders.get(r["id"], {}),
        }
        (material if r["materiality"] == "material" else routine).append(item)

    by_cat: dict[str, int] = {}
    for item in routine:
        by_cat[item["category"]] = by_cat.get(item["category"], 0) + 1

    total = len(material) + len(routine)
    rules_pct = round(100 * sum(1 for i in material + routine if i["rules_handled"]) / total, 1) if total else 0.0
    return {
        "window_hours": window_hours,
        "stats": {"total": total, "material": len(material), "routine": len(routine), "rules_pct": rules_pct},
        "routine_collapsed": {"by_category": by_cat, "items": routine},
        "material": material,
    }
