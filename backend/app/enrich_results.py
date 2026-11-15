import io
import json
import re

from . import db, llm, nse_client
from .config import BACKEND_DIR

FILINGS_DIR = BACKEND_DIR / "data" / "filings"

RESULTS_HEADLINE = re.compile(r"outcome of board meeting|financial result|results", re.I)
NOT_RESULTS = re.compile(r"newspaper|advertisement|transcript|intimation of record", re.I)
SCANNED_PAGE_CHARS = 80


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


def is_scanned(pages: list[str], page_idx: list[int]) -> bool:
    return sum(len(pages[i].strip()) for i in page_idx if i < len(pages)) < SCANNED_PAGE_CHARS * len(page_idx)


def render_pages_png(pdf_path, page_idx: list[int], scale: float = 2.5) -> list[bytes]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    out = []
    for i in page_idx:
        if i >= len(pdf):
            continue
        bitmap = pdf[i].render(scale=scale)
        pil = bitmap.to_pil()
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


def _num_ok(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and abs(x) < 1e9


def _normalize(s: str) -> str:
    return re.sub(r"[\s,]", "", s)


def _num_variants(v: float) -> list[str]:
    out = []
    if float(v) == int(v):
        out.append(str(int(v)))
    out.append(f"{v:.2f}".rstrip("0").rstrip("."))
    out.append(f"{v:.1f}")
    out.append(f"{v:.0f}")
    return list(dict.fromkeys(out))


def _find_page(pages: list[int], page_texts: dict[int, str], value) -> int | None:
    if not _num_ok(value):
        return None
    for v in _num_variants(float(value)):
        needle = _normalize(v)
        for i in pages:
            if needle in _normalize(page_texts.get(i, "")):
                return i + 1
    return None


def verify_rows(card: dict, pages: list[str], page_idx: list[int]) -> dict:
    page_texts = {i: pages[i] for i in page_idx if i < len(pages)}
    kept = []
    for r in card.get("rows", []):
        page = _find_page(page_idx, page_texts, r.get("current"))
        if page is None:
            continue
        r["page"] = page
        kept.append(r)
    card["rows"] = kept
    card["source"] = {"doc": "results filing", "page": str(kept[0]["page"]) if kept else ""}
    return card


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
    rev = next((v for l, v in by_label.items() if "revenue" in l or "sales" in l), None)
    if rev and pat and rev.get("current") is not None and pat.get("current") is not None:
        if rev["current"] > 0 and pat["current"] > rev["current"]:
            return False
    return True


EXTRACT_SCHEMA = (
    "Return STRICT JSON: {\"period\": \"e.g. Q2 FY27 (Sep 2026 quarter)\", \"currency_unit\": \"Rs Cr|Rs L|Rs|INR Mn\", "
    "\"rows\": [{\"label\": \"Revenue|EBITDA|PBT|PAT\", \"current\": <num>, \"prev_quarter\": <num|null>, \"year_ago\": <num|null>}]}\n"
    "Rules: numbers in the filing's own unit (state it). EBITDA = profit before tax + finance cost + depreciation if EBITDA not stated. "
    "prev_quarter = the sequential comparison column; year_ago = the same-quarter-last-year column. Use null if a column is absent. "
    "Copy numbers EXACTLY as printed (do not convert units)."
)


def _finalize(data: dict, ticker: str, page_idx: list[int], confidence: str, source_type: str) -> dict | None:
    unit = data.get("currency_unit") or "Rs Cr"
    rows = []
    for r in data.get("rows", []):
        cur, pq, ya = r.get("current"), r.get("prev_quarter"), r.get("year_ago")
        if not _num_ok(cur):
            continue
        qoq = round(100 * (cur - pq) / abs(pq), 1) if _num_ok(pq) and pq != 0 else None
        yoy = round(100 * (cur - ya) / abs(ya), 1) if _num_ok(ya) and ya != 0 else None
        page = (page_idx[0] + 1) if page_idx else None
        rows.append({"label": r.get("label", "?"), "current": cur, "qoq": qoq, "yoy": yoy,
                     "page": page if source_type == "scanned" else None})
    if not rows:
        return None
    return {
        "ticker": ticker,
        "period": data.get("period", ""),
        "currency": unit,
        "rows": rows,
        "source": {"doc": "results filing", "page": str(page_idx[0] + 1) if page_idx else ""},
        "source_type": source_type,
        "confidence": confidence,
    }


def _unit_to_crore_mult(unit: str) -> float:
    u = (unit or "").lower()
    if "crore" in u or " cr" in u or u.endswith("cr"):
        return 1.0
    if "lakh" in u or " lac" in u or u.endswith("l"):
        return 0.01
    if "mn" in u or "million" in u:
        return 10.0
    if u in ("rs", "inr", "₹"):
        return 1e-7
    return 1.0


def normalize_to_crore(card: dict) -> dict:
    mult = _unit_to_crore_mult(card.get("currency", ""))
    if mult == 1.0:
        card["currency"] = "Rs Cr"
        return card
    for r in card.get("rows", []):
        for k in ("current",):
            if _num_ok(r.get(k)):
                r[k] = round(r[k] * mult, 2)
    card["currency"] = "Rs Cr"
    return card


def dedupe_cards() -> int:
    """One card per (ticker, period): keep the one with the most verified rows."""
    import json as _json

    removed = 0
    with db.get_db() as conn:
        rows = conn.execute(
            """SELECT r.id, r.announcement_id, r.payload_json, a.ticker, a.headline
               FROM renders r JOIN announcements a ON a.id = r.announcement_id
               WHERE r.kind = 'results_card'"""
        ).fetchall()
    groups: dict[tuple, list] = {}
    for r in rows:
        if '"skipped"' in r["payload_json"]:
            continue
        try:
            card = _json.loads(r["payload_json"])
        except ValueError:
            continue
        key = (card.get("ticker", r["ticker"]), card.get("period", ""))
        groups.setdefault(key, []).append((r, len(card.get("rows", []))))
    for key, items in groups.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: -x[1])
        for loser, _ in items[1:]:
            with db.get_db() as conn:
                conn.execute("DELETE FROM renders WHERE id = ?", (loser["id"],))
                conn.execute(
                    "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'results_card', ?)",
                    (loser["announcement_id"], _json.dumps({"skipped": f"duplicate of {key[0]} {key[1]}"})),
                )
            removed += 1
    return removed


def build_results_card(ann_id: int, ticker: str, pdf_url: str, subject: str) -> dict | None:
    text, pages = extract_pdf_text(pdf_url, ticker)
    if not pages:
        return None
    page_idx = select_results_pages(pages)
    if not page_idx:
        return None
    scanned = is_scanned(pages, page_idx)
    pdf_path = FILINGS_DIR / ticker / (pdf_url.split("/")[-1].split("?")[0] or "results.pdf")

    if scanned:
        images = render_pages_png(pdf_path, page_idx)
        if not images:
            return None
        page_list = ", ".join(str(i + 1) for i in page_idx if i < len(pages))
        prompt = (
            f"These are scanned page(s) {page_list} of an Indian company's quarterly financial results filing. "
            "Read the tables in the images and extract the headline numbers.\n" + EXTRACT_SCHEMA
        )
        data = llm.call_json("results_extract_scanned", prompt, tier="cheap", images=images)
        card = _finalize(data, ticker, page_idx, "high-scanned", "scanned") if data else None
        if card and sanity_check(card):
            return normalize_to_crore(card)
        data2 = llm.call_json("results_extract_scanned_strong", prompt, tier="strong", images=images)
        card = _finalize(data2, ticker, page_idx, "strong-recheck-scanned", "scanned") if data2 else None
        if card and sanity_check(card):
            return normalize_to_crore(card)
        return None

    chunk = "\n".join(f"[[PAGE {i+1}]]\n{pages[i]}" for i in page_idx)[:14000]
    prompt = (
        "This is an Indian company's quarterly financial results filing (exchange filing). Extract the headline numbers.\n"
        + EXTRACT_SCHEMA + "\n\n" + chunk
    )
    data = llm.call_json("results_extract", prompt, tier="cheap")
    card = _finalize(data, ticker, page_idx, "high", "text") if data else None
    if card:
        card = verify_rows(card, pages, page_idx)
        if sanity_check(card):
            return normalize_to_crore(card)
    strong = llm.call_json("results_extract_strong", prompt, tier="strong")
    card = _finalize(strong, ticker, page_idx, "strong-recheck", "text") if strong else None
    if card:
        card = verify_rows(card, pages, page_idx)
        if sanity_check(card):
            return normalize_to_crore(card)
    return None


def enrich_results() -> int:
    n = 0
    with db.get_db() as conn:
        pending = conn.execute(
            """SELECT a.id, a.ticker, a.pdf_url, a.subject, a.headline FROM announcements a
               LEFT JOIN renders r ON r.announcement_id = a.id AND r.kind = 'results_card'
               WHERE a.category = 'results' AND a.pdf_url IS NOT NULL AND a.pdf_url != '' AND r.id IS NULL
               ORDER BY a.priority DESC LIMIT 20"""
        ).fetchall()
    for row in pending:
        blob = f"{row['headline']} {row['subject'] or ''}"
        if NOT_RESULTS.search(blob) or not RESULTS_HEADLINE.search(blob):
            with db.get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'results_card', ?)",
                    (row["id"], json.dumps({"skipped": "not a statement filing"})),
                )
            continue
        card = build_results_card(row["id"], row["ticker"], row["pdf_url"], row["subject"])
        if card:
            with db.get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'results_card', ?)",
                    (row["id"], json.dumps(card)),
                )
            n += 1
        else:
            with db.get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'results_card', ?)",
                    (row["id"], json.dumps({"skipped": "extraction failed sanity checks"})),
                )
    dedupe_cards()
    return n
