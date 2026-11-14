import json
import re

from . import db, llm
from .config import WATCH_TYPES

CATEGORIES = list(WATCH_TYPES.keys())

MATERIAL_CATEGORIES = {"results", "mna", "fund_raise", "management_change", "litigation", "insider_trading", "pledging", "credit_rating", "capex", "bonus_split"}

PRIORITY = {
    "results": 95, "mna": 90, "management_change": 85, "litigation": 85,
    "fund_raise": 80, "pledging": 80, "insider_trading": 75, "credit_rating": 60,
    "capex": 60, "bonus_split": 55, "dividend": 50, "press_release": 45,
    "earnings_call": 30, "investor_meetings": 20, "postal_ballot": 15, "agm_egm": 15,
    "unclassified": 10,
}

RULES: list[tuple[str, re.Pattern]] = [
    ("management_change", re.compile(r"change in director|change in kmp|chief financial officer|company secretary|appointment of .*(director|ceo|cfo|md|manager)|resignation|retirement of|cessation of", re.I)),
    ("results", re.compile(r"financial result|audited result|unaudited result|declaration of financial|outcome of board meeting|notice of board meeting", re.I)),
    ("dividend", re.compile(r"dividend", re.I)),
    ("bonus_split", re.compile(r"bonus issue|stock split|sub-?division of|split of shares|fractional shares", re.I)),
    ("fund_raise", re.compile(r"fund rais|fundrais|preferential issue|preferential allot|qualified institutional|qip|rights issue|commercial paper|non-convertible debenture|ncds|issue of (shares|securities|debentures)|borrowing", re.I)),
    ("mna", re.compile(r"acquisition|merger|amalgamat|demerger|joint venture|scheme of arrangement|stake in|acquire[sd]? ", re.I)),
    ("litigation", re.compile(r"penalt|imposition of (fine|monetary)|order from |sebi order|show cause|insolvency|bankruptcy|winding up|nclt|ibc|legal proceeding|tax demand|adjudication", re.I)),
    ("insider_trading", re.compile(r"sast|regulation 29\(2\)|acquisition/sale of shares|sale of shares by|purchase of shares by|disclosure under pit|trade receive", re.I)),
    ("credit_rating", re.compile(r"credit rating|rating (assign|reaffirm|upgrad|downgrad|withdraw)|crisil|icra|care ratings|india ratings|moody|fitch", re.I)),
    ("capex", re.compile(r"capex|capacity expansion|new (plant|facility|manufacturing)|setting up of|greenfield|investment in .*(plant|facility|subsidiary)", re.I)),
    ("pledging", re.compile(r"pledge|encumbran|release of (shares|security)|creation of (charge|security)", re.I)),
    ("postal_ballot", re.compile(r"postal ballot|e-?voting result|remote e-?voting", re.I)),
    ("agm_egm", re.compile(r"annual general meeting|extraordinary general meeting|\bagm\b|\begm\b|court convened|annual report", re.I)),
    ("earnings_call", re.compile(r"earnings call|con\.? ?call|conference call|transcript of|recording of|intimation of (earnings|concall)|schedule of analyst", re.I)),
    ("investor_meetings", re.compile(r"analysts?/institutional|investor meet|one[- ]on[- ]one|schedule of meet|participat\w* in the institution", re.I)),
    ("press_release", re.compile(r"bagging/receiving|order (win|receiv|secu)|press release|media release|contract|communique|partnership|mou", re.I)),
    ("unclassified", re.compile(r"esop|share certificate|compliance (certificate|report)|regulation 7\(3\)|shareholding (pattern|for the period)|investor grievance|statement of deviation|listing fee|intimation under reg|certificate under reg|loss of share|newspaper publication|newspaper advertisement", re.I)),
]

AMBIGUOUS_HEADERS = {"general updates", "updates", "outcome of board meeting", "press release", "announcement", "other disclosures", "general"}


def rules_classify(headline: str, subject: str) -> tuple[str | None, bool]:
    """Returns (category, rules_handled). Ambiguous headers only matched via subject."""
    h = headline or ""
    for cat, rx in RULES:
        if rx.search(h):
            if h.strip().lower() in AMBIGUOUS_HEADERS:
                break
            return cat, True
    s = f"{headline} {subject}"[:600]
    for cat, rx in RULES:
        if rx.search(s):
            return cat, True
    return None, False


def priority_score(category: str, published_at: str | None) -> float:
    score = PRIORITY.get(category, 10)
    if WATCH_TYPES.get(category):
        score += 15
    return float(score)


def llm_batch_classify(items: list[dict]) -> list[dict]:
    if not items:
        return []
    lines = [
        {"i": i, "ticker": it["ticker"], "headline": it["headline"], "subject": (it["subject"] or "")[:220]}
        for i, it in enumerate(items)
    ]
    prompt = (
        "You classify Indian corporate exchange announcements (NSE). For each item, output a JSON array of objects:\n"
        '{"i": <int>, "category": <one of: results, mna, fund_raise, management_change, litigation, insider_trading, '
        'earnings_call, investor_meetings, credit_rating, dividend, bonus_split, capex, press_release, postal_ballot, agm_egm, pledging, unclassified>, '
        '"materiality": <"material"|"routine">, "summary": <one-line summary, max 90 chars, factual>}\n'
        'Materiality: "material" only if it could move the stock (results, M&A, fund raise, top-management change, litigation/regulatory action, '
        "insider/promoter share moves, pledging, rating change, capex, bonus/split). Routine = compliance paperwork, ESOPs, investor meetings, "
        "concall notices, dividends, AGM/EGM notices, generic updates.\n"
        "Items:\n" + json.dumps(lines, ensure_ascii=False)
    )
    out = llm.call_json("classify_batch", prompt, tier="cheap")
    if not out or not isinstance(out, list):
        return [{"i": i, "category": "unclassified", "materiality": "routine", "summary": None, "llm_failed": True} for i in range(len(items))]
    return out


def classify_all() -> dict:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT id, ticker, headline, subject FROM announcements WHERE category IS NULL ORDER BY id"
        ).fetchall()
    stats = {"total": len(rows), "rules": 0, "llm": 0, "llm_failed": 0}
    llm_items, llm_ids = [], []
    for r in rows:
        cat, handled = rules_classify(r["headline"], r["subject"])
        if cat:
            stats["rules"] += 1
            with db.get_db() as conn:
                _apply(conn, r["id"], cat, "material" if cat in MATERIAL_CATEGORIES else "routine", None, 1)
        else:
            llm_items.append(dict(r))
            llm_ids.append(r["id"])
    if llm_items:
        results = llm_batch_classify(llm_items)
        by_i = {o.get("i"): o for o in results if isinstance(o, dict)}
        for idx, (item, aid) in enumerate(zip(llm_items, llm_ids)):
            o = by_i.get(idx, {})
            cat = o.get("category", "unclassified")
            if cat not in CATEGORIES:
                cat = "unclassified"
            mat = o.get("materiality", "routine")
            if mat not in ("material", "routine"):
                mat = "routine"
            summary = o.get("summary")
            if o.get("llm_failed") or (not o and not llm.configured()):
                stats["llm_failed"] += 1
            else:
                stats["llm"] += 1
            with db.get_db() as conn:
                _apply(conn, aid, cat, mat, summary, 0)
    total = stats["total"] or 1
    stats["rules_pct"] = round(100 * stats["rules"] / total, 1)
    stats["llm_pct"] = round(100 * stats["llm"] / total, 1)
    return stats


def _apply(conn, ann_id: int, category: str, materiality: str, summary: str | None, rules_handled: int) -> None:
    conn.execute(
        """UPDATE announcements SET category = ?, materiality = ?, summary = COALESCE(?, summary), rules_handled = ?,
               priority = ? + CASE WHEN published_at LIKE '%2026-11-15%' OR published_at LIKE '%15-Nov-2026%' THEN 5 ELSE 0 END
           WHERE id = ?""",
        (category, materiality, summary, rules_handled, priority_score(category, None), ann_id),
    )


if __name__ == "__main__":
    print(json.dumps(classify_all(), indent=1))
