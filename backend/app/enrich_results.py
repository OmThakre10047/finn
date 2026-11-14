import json
import re

from . import db, llm, nse_client
from .config import BACKEND_DIR

FILINGS_DIR = BACKEND_DIR / "data" / "filings"
METRICS = ["Revenue", "EBITDA", "PBT", "PAT"]


def extract_pdf_text(url: str, ticker: str) -> tuple[str, list[str]]:
    dest = FILINGS_DIR / ticker / (url.split("/")[-1].split("?")[0] or "results.pdf")
    ok = nse_client.download_pdf(url, dest)
    if not ok:
        return "", []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(dest))
        pages = [(p.extract_text() or "") for p in reader.pages]
        return "\n".join(f"[[PAGE {i+1}]]\n{t}" for i, t in enumerate(pages)), pages
    except Exception:
        return "", []


def select_results_pages(pages: list[str]) -> list[int]:
    scores = []
    for i, t in enumerate(pages):
        tl = t.lower()
        s = 0
        for kw in ("financial results", "revenue from operations", "profit before tax", "profit after tax",
                   "profit for the period", "quarter ended", "statement of"):
            if kw in tl:
                s += 3
        if "ebitda" in tl or "depreciation" in tl:
            s += 2
        scores.append(s)
    if not scores or max(scores) == 0:
        return list(range(min(6, len(pages))))
    best = sorted(range(len(pages)), key=lambda i: -scores[i])[:4]
    return sorted(best)


def _num_ok(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and abs(x) < 1e9


def sanity_check(card: dict) -> bool:
    rows = card.get("rows") or []
    if not isinstance(rows, list) or len(rows) < 3:
        return False
    labels = {str(r.get("label", "")).lower() for r in rows}
    if not any("revenue" in l for l in labels):
        return False
    for r in rows:
        if not _num_ok(r.get("current")):
            return False
        for k in ("qoq", "yoy"):
            v = r.get(k)
            if v is not None and (not _num_ok(v) or abs(v) > 300):
                return False
    by_label = {str(r.get("label", "")).lower(): r for r in rows}
    pat = next((v for l, v in by_label.items() if "pat" in l or "net profit" in l), None)
    pbt = next((v for l, v in by_label.items() if "pbt" in l or "profit before tax" in l), None)
    if pat and pbt and pat.get("current") is not None and pbt.get("current") is not None:
        if pat["current"] > pbt["current"] * 1.05:
            return False
    return True


def build_results_card(ann_id: int, ticker: str, pdf_url: str, subject: str) -> dict | None:
    text, pages = extract_pdf_text(pdf_url, ticker)
    if not pages:
        return None
    page_idx = select_results_pages(pages)
    chunk = "\n".join(f"[[PAGE {i+1}]]\n{pages[i]}" for i in page_idx)[:14000]
    prompt = (
        "This is an Indian company's quarterly financial results filing (exchange filing). Extract the headline numbers.\n"
        "Return STRICT JSON: {\"period\": \"e.g. Q2 FY27 (Sep 2026 quarter)\", \"currency_unit\": \"Rs Cr|Rs L|Rs\", "
        "\"rows\": [{\"label\": \"Revenue|EBITDA|PBT|PAT\", \"current\": <num>, \"prev_quarter\": <num|null>, \"year_ago\": <num|null>}]}\n"
        "Rules: numbers in the filing's own unit (state it). EBITDA = profit before tax + finance cost + depreciation if EBITDA not stated. "
        "prev_quarter = the sequential comparison column; year_ago = the same-quarter-last-year column. Use null if a column is absent. "
        "Copy numbers EXACTLY as printed (do not convert units).\n\n" + chunk
    )
    data = llm.call_json("results_extract", prompt, tier="cheap")
    card = None
    if data and isinstance(data.get("rows"), list):
        card = _finalize(data, ticker, page_idx, "high")
        if card and sanity_check(card):
            return card
    strong = llm.call_json("results_extract_strong", prompt, tier="strong")
    if strong and isinstance(strong.get("rows"), list):
        card = _finalize(strong, ticker, page_idx, "strong-recheck")
        if card and sanity_check(card):
            return card
    return card if card and sanity_check(card) else None


def _finalize(data: dict, ticker: str, page_idx: list[int], confidence: str) -> dict | None:
    unit = data.get("currency_unit") or "Rs Cr"
    rows = []
    for r in data["rows"]:
        cur, pq, ya = r.get("current"), r.get("prev_quarter"), r.get("year_ago")
        if not _num_ok(cur):
            continue
        qoq = round(100 * (cur - pq) / abs(pq), 1) if _num_ok(pq) and pq != 0 else None
        yoy = round(100 * (cur - ya) / abs(ya), 1) if _num_ok(ya) and ya != 0 else None
        rows.append({"label": r.get("label", "?"), "current": cur, "qoq": qoq, "yoy": yoy})
    if not rows:
        return None
    src_page = (page_idx[0] + 1) if page_idx else None
    return {
        "ticker": ticker,
        "period": data.get("period", ""),
        "currency": unit,
        "rows": rows,
        "source": {"doc": "results filing", "page": str(src_page) if src_page else ""},
        "confidence": confidence,
    }


def enrich_results() -> int:
    n = 0
    with db.get_db() as conn:
        pending = conn.execute(
            """SELECT a.id, a.ticker, a.pdf_url, a.subject FROM announcements a
               LEFT JOIN renders r ON r.announcement_id = a.id AND r.kind = 'results_card'
               WHERE a.category = 'results' AND a.pdf_url IS NOT NULL AND a.pdf_url != '' AND r.id IS NULL
               ORDER BY a.priority DESC LIMIT 10"""
        ).fetchall()
    for row in pending:
        card = build_results_card(row["id"], row["ticker"], row["pdf_url"], row["subject"])
        if card:
            with db.get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'results_card', ?)",
                    (row["id"], json.dumps(card)),
                )
            n += 1
    return n
