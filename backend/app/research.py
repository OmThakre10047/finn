import hashlib
import json
import re
import threading
from datetime import datetime, timedelta

from . import db, llm, nse_client, screener
from .config import BACKEND_DIR

FILINGS_DIR = BACKEND_DIR / "data" / "filings"
CALL_CHAR_CAP = 240_000  # ~60k tokens per cheap call
SECTIONS = [
    "business_snapshot", "financial_snapshot", "trajectory", "balance_sheet",
    "cash_quality", "narrative_vs_numbers", "guidance", "bull_vs_bear",
]

AR_SECTIONS: dict[str, list[str]] = {
    "business_mda": [r"business overview", r"our business", r"corporate overview", r"management discussion", r"management's discussion", r"m\.?d\.?&?a\.?", r"segment"],
    "balance_sheet": [r"balance sheet", r"statement of assets and liabilities"],
    "cash_flow": [r"cash flow"],
    "borrowings": [r"borrowing", r"long[- ]term loan", r"debt"],
    "contingent_liabilities": [r"contingent liabilit"],
    "related_party": [r"related party"],
    "auditor_report": [r"auditor's report", r"independent auditor"],
}
AR_ALWAYS = {"auditor_report", "contingent_liabilities", "related_party"}
AR_MAX_PAYLOADS = 3


def _doc_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _pdf_path(ticker: str, url: str):
    name = url.split("/")[-1].split("?")[0] or f"{_doc_id(url)}.pdf"
    return FILINGS_DIR / ticker / name


def _doc_pages(ticker: str, url: str) -> list[str]:
    path = _pdf_path(ticker, url)
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM filings WHERE ticker = ? AND url = ?", (ticker, url)).fetchone()
    if row and row["path"] and (BACKEND_DIR / row["path"]).exists():
        path = BACKEND_DIR / row["path"]
    elif not nse_client.download_pdf(url, path):
        return []
    pages: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        for i in range(len(reader.pages)):
            try:
                pages.append(reader.pages[i].extract_text() or "")
            except Exception:
                pages.append("")
    except Exception:
        pages = []
    if not pages or sum(len(p) for p in pages) < 500:
        pages = []
        try:
            import pdfplumber

            with pdfplumber.open(str(path)) as pdf:
                for p in pdf.pages:
                    try:
                        pages.append(p.extract_text() or "")
                    except Exception:
                        pages.append("")
        except Exception:
            pages = []
    with db.get_db() as conn:
        conn.execute(
            """INSERT INTO filings (ticker, kind, url, path, content_hash) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(ticker, kind, url) DO UPDATE SET path = excluded.path, content_hash = excluded.content_hash""",
            (ticker, "doc", url, str(path.relative_to(BACKEND_DIR)), _doc_id("".join(pages) or url)),
        )
    return pages


TOC_LINE = re.compile(r"\.{3,}\s*\d+\s*$")


def _select_ar_pages(pages: list[str]) -> tuple[list[int], dict[str, list[int]]]:
    """Heading-based page index. TOC lines filtered; up to 3 occurrences per section
    (heading page +1 each); auditor/CL/RPT always included; round-robin budget so every
    section gets pages. Returns (indices, {section: [page indices chosen]})."""
    buckets: dict[str, list[int]] = {}
    for i, t in enumerate(pages):
        for line in t.split("\n")[:40]:
            line_s = line.strip()
            if len(line_s) < 4 or len(line_s) > 90 or TOC_LINE.search(line_s):
                continue
            lowered = line_s.lower()
            for sec, kws in AR_SECTIONS.items():
                if any(re.search(kw, lowered) for kw in kws):
                    occ = buckets.setdefault(sec, [])
                    if i not in occ and len(occ) < 6:
                        occ.extend([i, i + 1] if i + 1 < len(pages) else [i])
                    break
    if not buckets:
        fallback = list(range(min(30, len(pages))))
        return fallback, {"fallback_head": fallback}
    ordered_secs = [s for s in AR_SECTIONS if s in buckets]
    ordered_secs.sort(key=lambda s: (s not in AR_ALWAYS, s))
    total_budget = AR_MAX_PAYLOADS * CALL_CHAR_CAP * 0.9
    used, chosen, sec_pages = 0, [], {}
    rounds = max(len(b) // 2 for b in buckets.values())
    for rnd in range(rounds):
        for s in ordered_secs:
            occ = buckets[s]
            batch = occ[rnd * 2:rnd * 2 + 2]
            if not batch:
                continue
            cost = sum(len(pages[i]) for i in batch if i < len(pages))
            if used + cost > total_budget and s in sec_pages:
                continue
            chosen.extend(batch)
            used += cost
            sec_pages.setdefault(s, []).extend(batch)
    indices = sorted(set(chosen))
    return indices, sec_pages


def _ar_payloads(pages: list[str]) -> tuple[list[str], dict[str, int]]:
    indices, sec_pages = _select_ar_pages(pages)
    payloads = _split_into_payloads(pages, indices, max_payloads=AR_MAX_PAYLOADS)
    kept: set[int] = set()
    for p in payloads:
        kept.update(int(m) - 1 for m in re.findall(r"\[\[PAGE (\d+)\]\]", p))
    log = {}
    for sec, plist in sec_pages.items():
        n = len([pg for pg in plist if pg in kept])
        if n:
            log[sec] = n
    return payloads, log


def _mark(pages: list[str], indices: list[int]) -> str:
    return "\n".join(f"[[PAGE {i+1}]]\n{pages[i]}" for i in indices)


def _split_into_payloads(pages: list[str], indices: list[int], max_payloads: int = 2) -> list[str]:
    payloads, cur, cur_chars = [], [], 0
    for i in indices:
        t = f"[[PAGE {i+1}]]\n{pages[i]}"
        if cur and cur_chars + len(t) > CALL_CHAR_CAP:
            payloads.append("\n".join(cur))
            cur, cur_chars = [], 0
            if len(payloads) == max_payloads:
                break
        cur.append(t)
        cur_chars += len(t)
    if cur and len(payloads) < max_payloads:
        payloads.append("\n".join(cur))
    return payloads


def sections_in_str(sections_log: dict[str, int]) -> str:
    return ", ".join(f"{k}:{n}p" for k, n in sections_log.items())


def _extract_from_doc(ticker: str, kind: str, period: str, url: str, payload_picker) -> dict:
    pages = _doc_pages(ticker, url)
    if not pages:
        return {"doc": f"{kind} {period}".strip(), "period": period, "facts": [], "promises": [], "valid_pages": set(), "unavailable": True}
    doc_label = f"{kind} {period}".strip()
    payloads, sections_log = payload_picker(pages)
    if sections_log:
        print(f"[research] {doc_label}: sections included: {sections_in_str(sections_log)}", flush=True)
    facts, promises = [], []
    valid_pages: set[int] = set()
    for payload in payloads:
        for m in re.finditer(r"\[\[PAGE (\d+)\]\]", payload):
            valid_pages.add(int(m.group(1)))
        prompt = (
            f"You are reading part of the {doc_label} of Indian listed company {ticker}. Text has [[PAGE n]] markers.\n"
            "Extract, citing every item with its page number:\n"
            '1. "facts": key business/financial facts (business model, segments, revenue mix, margins, debt, working capital, '
            "cash flow, capex, ROCE, auditor flags, contingent liabilities, related-party notes) — max 25, most decision-relevant.\n"
            '2. "promises": forward-looking commitments (growth %, margin %, revenue targets, capex plans, order book, '
            "launches, timelines) — ALL you can find, each with period_promised = the reporting period of this document.\n"
            'Return STRICT JSON: {"facts": [{"topic","note","page"}], "promises": [{"promise","metric","target","period_promised","page"}]}\n'
            "Only what is explicitly in the text. No outside knowledge.\n\n" + payload
        )
        out = llm.call_json(f"research_extract:{ticker}:{doc_label}", prompt, tier="cheap")
        if isinstance(out, dict):
            for f in out.get("facts", []):
                f["doc"] = doc_label
            facts.extend(out.get("facts", []))
            for p in out.get("promises", []):
                p["doc"] = doc_label
            promises.extend(out.get("promises", []))
    return {"doc": doc_label, "period": period, "facts": facts, "promises": promises, "valid_pages": valid_pages}


def _quarterly_actuals(screener_data: dict) -> dict:
    q = screener_data.get("quarterly") or {}
    periods, rows = q.get("periods") or [], q.get("rows") or {}
    last = periods[-8:] if len(periods) > 8 else periods
    out = {"periods": last}
    for name, vals in rows.items():
        out[name] = vals[-8:] if len(vals) > 8 else vals
    return out


def _synthesise(ticker: str, name: str, extractions: list[dict], actuals: dict, top_ratios: dict) -> dict:
    facts, promises = [], []
    for e in extractions:
        facts.extend(e.get("facts", []))
        promises.extend(e.get("promises", []))
    doc_labels = [e["doc"] for e in extractions]
    common = (
        f"Company: {ticker} ({name}). Build STRICTLY from the primary-source material below "
        "(facts extracted from its annual report + concall transcripts, and standardized quarterly actuals from filings). "
        "No outside knowledge, no news.\n\n"
        f"AVAILABLE DOCUMENT LABELS: {json.dumps(doc_labels)}\n"
        f"QUARTERLY ACTUALS (screener-standardized, Rs Cr unless stated):\n{json.dumps(actuals, ensure_ascii=False)}\n\n"
        f"SNAPSHOT RATIOS: {json.dumps(top_ratios, ensure_ascii=False)}\n\n"
        f"FACTS FROM PRIMARY DOCS (doc + page):\n{json.dumps(facts[:80], ensure_ascii=False)}\n\n"
        f"MANAGEMENT PROMISES FROM TRANSCRIPTS (doc + period + page):\n{json.dumps(promises[:60], ensure_ascii=False)}\n\n"
        "Rules: use EXACT document labels from AVAILABLE DOCUMENT LABELS in every citation. "
        "'quarter_key' = the specific quarter (e.g. 'Sep 2026') the promise was about, or null if unclear. "
        "'delivered' must come from QUARTERLY ACTUALS only; 'unverifiable' if actuals don't cover it. "
        "Sections: 80-150 words, concrete, every number cited.\n\n"
    )
    sections_prompt = common + (
        'Return STRICT JSON: {"sections": {'
        '"business_snapshot": {"title","text","citations":[{"doc","period","page"}]}, '
        '"financial_snapshot": {...}, "trajectory": {...}, "balance_sheet": {...}, "cash_quality": {...}, '
        '"narrative_vs_numbers": {...}, "guidance": {...}, "bull_vs_bear": {...}}}'
    )
    tracker_prompt = common + (
        'Return STRICT JSON: {"promise_tracker": {"rows": [{"period_promised", "quarter_key", "promise", "metric", '
        '"target", "delivered", "verdict": "delivered|missed|partial|unverifiable", '
        '"citations": [{"doc","period","page"}]}]}}\n'
        "Include EVERY promise from MANAGEMENT PROMISES you can assess against the material."
    )
    sections, err1 = llm.call_json_strict(f"research_synthesis_sections:{ticker}", sections_prompt, tier="strong")
    if sections is None or not isinstance(sections.get("sections"), dict):
        raise RuntimeError(f"sections synthesis failed: {err1}")
    tracker, err2 = llm.call_json_strict(f"research_synthesis_tracker:{ticker}", tracker_prompt, tier="strong")
    if tracker is None or not isinstance(tracker.get("promise_tracker"), dict):
        print(f"[research] {ticker}: tracker synthesis failed ({err2}) — continuing without tracker", flush=True)
        tracker = {"promise_tracker": {"rows": []}}
    return {"sections": sections["sections"], "promise_tracker": tracker["promise_tracker"]}


def _validate_citations(report: dict, extractions: list[dict]) -> dict:
    labels = [e["doc"].lower() for e in extractions]
    valid: dict[str, set[int]] = {}
    for e in extractions:
        for page in e.get("valid_pages", set()):
            valid.setdefault(e["doc"].lower(), set()).add(int(page))

    def cite_ok(c: dict) -> bool:
        if not isinstance(c, dict):
            return False
        doc = str(c.get("doc", "")).lower().strip()
        page = c.get("page")
        if doc in ("screener", "quarterly actuals", "snapshot ratios"):
            return True
        for label in labels:
            if label in doc or doc in label:
                try:
                    return page is not None and int(page) in valid.get(label, set())
                except (TypeError, ValueError):
                    return False
        return False

    sections = {}
    for k, sec in (report.get("sections") or {}).items():
        if k not in SECTIONS:
            continue
        cites = [c for c in (sec.get("citations") or []) if cite_ok(c)]
        sections[k] = {**sec, "citations": cites}
    rows = []
    for r in (report.get("promise_tracker") or {}).get("rows", []):
        if not isinstance(r, dict):
            continue
        r["citations"] = [c for c in (r.get("citations") or []) if cite_ok(c)]
        if r["citations"]:
            rows.append(r)
    return {"sections": sections, "promise_tracker": {"rows": rows}}


def _pct_of(target: str):
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", str(target))
    return float(m.group(1)) if m else None


def _num_of(target: str):
    m = re.search(r"(-?\d[\d,]*(?:\.\d+)?)", str(target))
    return float(m.group(1).replace(",", "")) if m else None


def _row_for(actuals: dict, metric: str):
    ml = metric.lower()
    preferences = {
        "growth": ["yoy sales growth", "sales +"],
        "revenue": ["sales +", "revenue"],
        "sales": ["sales +"],
        "opm": ["opm %"],
        "margin": ["opm %"],
        "pat": ["net profit +"],
        "net profit": ["net profit +"],
        "profit": ["net profit +", "profit before tax"],
        "ebitda": ["operating profit"],
    }
    for key, candidates in preferences.items():
        if key in ml:
            for name, vals in actuals.get("rows", actuals).items():
                nl = name.lower()
                if any(c in nl for c in candidates):
                    return name, vals
    return None, None


def _numeric_verdicts(report: dict, actuals: dict) -> dict:
    def parse_val(v):
        try:
            return float(str(v).replace(",", "").replace("%", "").replace("(", "-").replace(")", ""))
        except (TypeError, ValueError):
            return None

    for r in (report.get("promise_tracker") or {}).get("rows", []):
        if not isinstance(r, dict):
            continue
        qk = r.get("quarter_key")
        idx = None
        for i, p in enumerate(actuals.get("periods", [])):
            if qk and (qk.lower() in p.lower() or p.lower() in qk.lower()):
                idx = i
                break
        if idx is None:
            continue
        metric = str(r.get("metric") or r.get("promise") or "")
        row_name, vals = _row_for(actuals, metric)
        if not vals or idx >= len(vals):
            continue
        actual = parse_val(vals[idx])
        if actual is None:
            continue
        pct = _pct_of(r.get("target", ""))
        num = _num_of(r.get("target", ""))
        target = pct if pct is not None else num
        if target is None:
            continue
        growth_like = any(w in metric.lower() for w in ("growth", "increase", "expand")) or (pct is not None and "margin" not in metric.lower() and "opm" not in metric.lower())
        if growth_like and pct is not None:
            r["delivered"] = f"{actual}% YoY"
        else:
            r["delivered"] = f"{actual} Rs Cr"
        ratio = actual / target if target else 0
        r["verdict"] = "delivered" if ratio >= 0.98 else ("partial" if ratio >= 0.9 else "missed")
    return report


def _finish_report(ticker: str) -> dict:
    data = screener.fetch_all(ticker)
    docs = data.get("documents") or {}
    concalls = sorted(
        docs.get("concalls", []),
        key=lambda d: screener.parse_period_date(d.get("period", "")) or datetime.min,
        reverse=True,
    )[:4]
    ars = sorted(docs.get("annual_reports", []), key=lambda d: screener.parse_period_date(d.get("period", d.get("label", ""))) or datetime.min, reverse=True)[:1]
    extractions = []
    sources = []
    def concall_picker(pages):
        return _split_into_payloads(pages, list(range(len(pages))), max_payloads=2), None

    for c in concalls:
        e = _extract_from_doc(ticker, "Concall", c.get("period", ""), c["url"], concall_picker)
        extractions.append(e)
        sources.append({"kind": "Concall", "period": c.get("period", ""), "url": c["url"]})
    for a in ars:
        label = a.get("period") or a.get("label", "")
        e = _extract_from_doc(ticker, "Annual Report", label, a["url"], _ar_payloads)
        extractions.append(e)
        sources.append({"kind": "Annual Report", "period": label, "url": a["url"]})
    actuals = _quarterly_actuals(data)
    ratios = data.get("top_ratios") or {}
    name = data.get("name") or ticker
    report = _synthesise(ticker, name, extractions, actuals, ratios)
    if not report or "sections" not in report:
        raise RuntimeError("synthesis failed")
    report = _validate_citations(report, extractions)
    report = _numeric_verdicts(report, actuals)
    return {
        "ticker": ticker,
        "name": name,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "sections": report["sections"],
        "promise_tracker": report["promise_tracker"],
        "sources": sources,
    }


def get_status(ticker: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM research_reports WHERE ticker = ?", (ticker.upper(),)).fetchone()
    if not row:
        return {"status": "missing"}
    if row["status"] == "error":
        try:
            msg = json.loads(row["payload_json"]).get("error", "unknown error") if row["payload_json"] else "unknown error"
        except ValueError:
            msg = "unknown error"
        return {"status": "error", "error": msg}
    if row["status"] == "done" and row["payload_json"]:
        try:
            return {"status": "done", "report": json.loads(row["payload_json"])}
        except ValueError:
            return {"status": "error", "error": "stored report is corrupt"}
    return {"status": row["status"] or "pending"}


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
                (json.dumps({"error": f"{type(e).__name__}: {str(e)[:400]}"}), ticker),
            )
