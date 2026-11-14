import hashlib
import json
import re
import threading
from datetime import datetime, timedelta

from . import db, llm, nse_client, screener
from .config import BACKEND_DIR

FILINGS_DIR = BACKEND_DIR / "data" / "filings"
MAX_DOC_CHARS = 400_000
SECTIONS = [
    "business_snapshot", "financial_snapshot", "trajectory", "balance_sheet",
    "cash_quality", "narrative_vs_numbers", "guidance", "bull_vs_bear",
]


def _doc_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _pdf_path(ticker: str, url: str):
    name = url.split("/")[-1].split("?")[0] or f"{_doc_id(url)}.pdf"
    return FILINGS_DIR / ticker / name


def _load_text(ticker: str, url: str) -> tuple[str, str]:
    """Returns (text_with_page_markers, period_label). Cached via filings table."""
    path = _pdf_path(ticker, url)
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM filings WHERE ticker = ? AND url = ?", (ticker, url)).fetchone()
    if row and row["path"] and (BACKEND_DIR / row["path"]).exists():
        text = (BACKEND_DIR / row["path"]).read_text(errors="ignore")
        return text, row["period"] or ""
    ok = nse_client.download_pdf(url, path)
    if not ok:
        return "", ""
    try:
        from pypdf import PdfReader

        pages = [(p.extract_text() or "") for p in PdfReader(str(path)).pages]
    except Exception:
        pages = []
    if not pages or sum(len(p) for p in pages) < 500:
        try:
            import pdfplumber

            with pdfplumber.open(str(path)) as pdf:
                pages = [(p.extract_text() or "") for p in pdf.pages]
        except Exception:
            pages = []
    text = "\n".join(f"[[PAGE {i+1}]]\n{t}" for i, t in enumerate(pages))[:MAX_DOC_CHARS]
    rel = path.relative_to(BACKEND_DIR)
    period = ""
    m = re.search(r"(20\d{2})", url.split("/")[-1])
    with db.get_db() as conn:
        conn.execute(
            """INSERT INTO filings (ticker, kind, url, period, path, content_hash) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker, kind, url) DO UPDATE SET path = excluded.path, content_hash = excluded.content_hash""",
            (ticker, "doc", url, period, str(rel), _doc_id(text or url)),
        )
    return text, period


def _extract_from_doc(ticker: str, kind: str, period: str, url: str) -> dict:
    text, _ = _load_text(ticker, url)
    if len(text) < 1000:
        return {"doc": kind, "period": period, "facts": [], "promises": [], "unavailable": True}
    doc_label = f"{kind} {period}".strip()
    prompt = (
        f"You are reading the {doc_label} of Indian listed company {ticker}. Text contains [[PAGE n]] markers.\n"
        "Extract, citing every item with the page number it came from:\n"
        '1. "facts": key business/financial facts (business model, segments, revenue mix, margins, debt, working capital, '
        "cash flow, capex, ROCE, auditor flags, contingent liabilities, related-party notes) — max 25, most decision-relevant.\n"
        '2. "promises": forward-looking commitments management makes (growth %, margin %, revenue targets, capex plans, '
        "order book, launches, timelines) — include the period it was said (e.g. Q2 FY27 call) — ALL you can find.\n"
        'Return STRICT JSON: {"facts": [{"topic": "...", "note": "...", "page": <int>}], '
        '"promises": [{"promise": "...", "metric": "...", "target": "...", "period_promised": "...", "page": <int>}]}\n'
        "Only include what is explicitly in the text. No outside knowledge.\n\n" + text
    )
    out = llm.call_json(f"research_extract:{ticker}:{doc_label}", prompt, tier="cheap")
    if not isinstance(out, dict):
        return {"doc": doc_label, "period": period, "facts": [], "promises": []}
    for f in out.get("facts", []):
        f["doc"] = doc_label
    for p in out.get("promises", []):
        p["doc"] = doc_label
    return {"doc": doc_label, "period": period, "facts": out.get("facts", []), "promises": out.get("promises", [])}


def _quarterly_actuals(screener_data: dict) -> dict:
    q = screener_data.get("quarterly") or {}
    periods, rows = q.get("periods") or [], q.get("rows") or {}
    last = periods[-8:] if len(periods) > 8 else periods
    out = {"periods": last}
    for name, vals in rows.items():
        out[name] = vals[-8:] if len(vals) > 8 else vals
    return out


def _synthesise(ticker: str, name: str, extractions: list[dict], actuals: dict, top_ratios: dict) -> dict:
    facts = []
    promises = []
    for e in extractions:
        facts.extend(e.get("facts", []))
        promises.extend(e.get("promises", []))
    facts_json = json.dumps(facts[:80], ensure_ascii=False)
    promises_json = json.dumps(promises[:60], ensure_ascii=False)
    actuals_json = json.dumps(actuals, ensure_ascii=False)
    prompt = (
        f"Build an investment research dossier for {ticker} ({name}) STRICTLY from the primary-source material below "
        "(facts extracted from its annual report + concall transcripts, and standardized quarterly actuals from filings). "
        "No outside knowledge, no news.\n\n"
        f"QUARTERLY ACTUALS (screener-standardized, Rs Cr unless stated):\n{actuals_json}\n\n"
        f"SNAPSHOT RATIOS: {json.dumps(top_ratios, ensure_ascii=False)}\n\n"
        f"FACTS FROM PRIMARY DOCS (each has doc + page):\n{facts_json}\n\n"
        f"MANAGEMENT PROMISES FROM TRANSCRIPTS (each has doc + period + page):\n{promises_json}\n\n"
        'Return STRICT JSON with keys:\n'
        '{"sections": {'
        '"business_snapshot": {"title": "...", "text": "...", "citations": [{"doc","period","page"}]}, '
        '"financial_snapshot": {...}, "trajectory": {...}, "balance_sheet": {...}, "cash_quality": {...}, '
        '"narrative_vs_numbers": {...}, "guidance": {...}, "bull_vs_bear": {...}}, '
        '"promise_tracker": {"rows": [{"period_promised", "promise", "metric", "target", "delivered", '
        '"verdict": "delivered|missed|partial|unverifiable", "citations": [{"doc","period","page"}]}]}}\n\n'
        "Rules: every citation must reference a doc+page present in the material. In promise_tracker, 'delivered' must quote "
        "or compute from QUARTERLY ACTUALS only; verdict 'unverifiable' if actuals don't cover it. Sections: concise, "
        "bullet-friendly, 80-150 words each. bull_vs_bear: two tight cases."
    )
    out = llm.call_json(f"research_synthesis:{ticker}", prompt, tier="strong")
    return out if isinstance(out, dict) else {}


def _finish_report(ticker: str) -> dict:
    data = screener.fetch_all(ticker)
    docs = data.get("documents") or {}
    concalls = sorted(docs.get("concalls", []), key=lambda d: d.get("period", ""), reverse=True)[:4]
    ars = sorted(docs.get("annual_reports", []), key=lambda d: d.get("period", ""), reverse=True)[:1]
    name = ""
    extractions = []
    sources = []
    for c in concalls:
        e = _extract_from_doc(ticker, "Concall", c.get("period", ""), c["url"])
        extractions.append(e)
        sources.append({"kind": "Concall", "period": c.get("period", ""), "url": c["url"]})
    for a in ars:
        e = _extract_from_doc(ticker, "Annual Report", a.get("period", a.get("label", "")), a["url"])
        extractions.append(e)
        sources.append({"kind": "Annual Report", "period": a.get("period", a.get("label", "")), "url": a["url"]})
    actuals = _quarterly_actuals(data)
    ratios = data.get("top_ratios") or {}
    name = ratios.get("High / Low", "") and ticker or ticker
    report = _synthesise(ticker, name, extractions, actuals, ratios)
    if not report or "sections" not in report:
        raise RuntimeError("synthesis failed")
    sections = {k: v for k, v in report.get("sections", {}).items() if k in SECTIONS}
    rows = report.get("promise_tracker", {}).get("rows", [])
    cited_rows = [r for r in rows if r.get("citations") and len(r["citations"]) > 0]
    return {
        "ticker": ticker,
        "name": name or ticker,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "sections": sections,
        "promise_tracker": {"rows": cited_rows},
        "sources": sources,
    }


def get_status(ticker: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM research_reports WHERE ticker = ?", (ticker.upper(),)).fetchone()
    if not row:
        return {"status": "missing"}
    if row["payload_json"]:
        try:
            return {"status": "done", "report": json.loads(row["payload_json"])}
        except ValueError:
            pass
    return {"status": row["status"]}


def start(ticker: str) -> dict:
    t = ticker.upper()
    st = get_status(t)
    if st["status"] == "done":
        with db.get_db() as conn:
            row = conn.execute("SELECT expires_at FROM research_reports WHERE ticker = ?", (t,)).fetchone()
        if row and row["expires_at"] and row["expires_at"] > datetime.utcnow().isoformat(timespec="seconds"):
            return {"status": "done", "report": st["report"]}
    with db.get_db() as conn:
        conn.execute(
            """INSERT INTO research_reports (ticker, status) VALUES (?, 'pending')
               ON CONFLICT(ticker) DO UPDATE SET status = 'pending', payload_json = NULL, generated_at = NULL""",
            (t,),
        )
    threading.Thread(target=_worker, args=(t,), daemon=True).start()
    return {"status": "pending"}


def _worker(ticker: str) -> None:
    try:
        report = _finish_report(ticker)
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat(timespec="seconds")
        with db.get_db() as conn:
            conn.execute(
                "UPDATE research_reports SET status = 'done', payload_json = ?, generated_at = ?, expires_at = ? WHERE ticker = ?",
                (json.dumps(report, ensure_ascii=False), report["generated_at"], expires, ticker),
            )
    except Exception as e:
        with db.get_db() as conn:
            conn.execute(
                "UPDATE research_reports SET status = 'error', payload_json = ? WHERE ticker = ?",
                (json.dumps({"error": str(e)[:300]}), ticker),
            )
