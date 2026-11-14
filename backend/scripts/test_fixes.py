#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import screener
from app.enrich_results import extract_pdf_text, select_results_pages, verify_rows, sanity_check
from app.research import _doc_pages, _select_ar_pages, _extract_calls, _validate_citations, _numeric_verdicts, CALL_CHAR_CAP
from app.config import BACKEND_DIR

PASS = []
def ok(name, cond, detail=""):
    PASS.append((name, cond))
    print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

data = screener.fetch_all("IRCTC")
docs = data["documents"]
concalls = sorted(docs["concalls"], key=lambda d: screener.parse_period_date(d.get("period","")) or screener.parse_period_date("Jan 1900"), reverse=True)
d0, dn = screener.parse_period_date(concalls[0]["period"]), screener.parse_period_date(concalls[-1]["period"])
ok("4a: concall labels parsed + sorted by date", len(concalls) >= 4 and d0 and dn and d0 > dn,
   f"first={concalls[0]['period']}, last={concalls[-1]['period']}, n={len(concalls)}")
ok("5: company name from screener", bool(data.get("name")), f"name={data.get('name')!r}")

print("\n-- 3: AR page index + call splitting --")
ar = docs["annual_reports"][0]
pages = _doc_pages("IRCTC", ar["url"])
ok("3: AR downloaded+extracted", len(pages) > 50, f"{len(pages)} pages")
sel = _select_ar_pages(pages)
ok("3: AR heading selection narrows", 10 <= len(sel) <= len(pages) // 2, f"selected {len(sel)}/{len(pages)} pages")
payloads = _extract_calls(pages, sel)
ok("3: AR payloads <=2 and under cap", 1 <= len(payloads) <= 2 and all(len(p) <= CALL_CHAR_CAP for p in payloads),
   f"{len(payloads)} payloads, max {max(len(p) for p in payloads)} chars")
cpage = _doc_pages("IRCTC", concalls[0]["url"])
cp = list(range(len(cpage)))
cpl = _extract_calls(cpage, cp)
ok("3: transcript split logic", 1 <= len(cpl) <= 2 and all(len(p) <= CALL_CHAR_CAP for p in cpl),
   f"{len(cpl)} payloads from {len(cpage)} pages")

print("\n-- 6: results-card number verification (real filing) --")
from app.nse_client import fetch_with_meta
rows_feed, _ = fetch_with_meta(7)
cand = next(r for r in rows_feed if r["ticker"] == "KAYNES" and r.get("pdf_url"))
ok("6: KAYNES SE-format statement filing found", bool(cand))
text, rpages = extract_pdf_text(cand["pdf_url"], "__TEST__")
idx = select_results_pages(rpages)
stmt = " ".join(rpages[i] for i in idx)
def grab(pat):
    mm = re.search(pat, stmt, re.I)
    return float(mm.group(1).replace(",", "")) if mm else None
real_num = grab(r"revenue from operations[^a-z]{0,80}?([\d,]+\.\d{1,2})")
ok("6: real revenue number found on selected pages", real_num is not None, f"{real_num}")
if real_num is not None:
    hit_page = next((i + 1 for i in idx if re.sub(r"[\s,]", "", str(real_num).rstrip("0").rstrip(".")) in re.sub(r"[\s,]", "", rpages[i])), None)
    pbt_num = grab(r"profit before tax[^a-z]{0,80}?([\d,]+\.\d{1,2})")
    pat_num = grab(r"profit for the period[^%]{0,120}?([\d,]+\.\d{1,2})")
    card = {"rows": [
        {"label": "Revenue", "current": real_num, "qoq": 1.0, "yoy": 2.0},
        {"label": "PBT", "current": pbt_num, "qoq": 1.0, "yoy": 2.0},
        {"label": "PAT", "current": pat_num, "qoq": 1.0, "yoy": 2.0},
        {"label": "FABRICATED", "current": 99999999, "qoq": 0, "yoy": 0},
    ]}
    v = verify_rows(card, rpages, idx)
    kept_labels = [r["label"] for r in v["rows"]]
    ok("6: verified number kept + page stored", "Revenue" in kept_labels and v["rows"][0].get("page") == hit_page, f"page={v['rows'][0].get('page')} (expected {hit_page})")
    ok("6: fabricated number dropped", "FABRICATED" not in kept_labels)
    ok("6: sanity_check accepts verified card", sanity_check(v), f"kept={kept_labels} (pbt={pbt_num}, pat={pat_num})")

print("\n-- 4c: numeric verdicts in Python --")
actuals = {"periods": ["Jun 2026", "Sep 2026"], "rows": {"YoY Sales growth": ["8.0", "12.0"], "OPM %": ["30", "31"], "Net Profit +": ["300", "350"]}}
rep = {"promise_tracker": {"rows": [
    {"period_promised": "Aug 2026 call", "quarter_key": "Sep 2026", "promise": "double-digit revenue growth", "metric": "revenue growth", "target": "12%", "delivered": "", "verdict": "unverifiable", "citations": [{"doc": "Concall Aug 2026", "period": "Aug 2026", "page": 3}]},
    {"period_promised": "Aug 2026 call", "quarter_key": "Sep 2026", "promise": "PAT of Rs 350 Cr", "metric": "PAT", "target": "Rs 350 Cr", "delivered": "", "verdict": "unverifiable", "citations": [{"doc": "Concall Aug 2026", "period": "Aug 2026", "page": 3}]},
    {"period_promised": "Aug 2026 call", "quarter_key": "Mar 2027", "promise": "future", "metric": "revenue growth", "target": "20%", "delivered": "", "verdict": "unverifiable", "citations": [{"doc": "Concall Aug 2026", "period": "Aug 2026", "page": 4}]},
]}}
out = _numeric_verdicts(rep, actuals)
rows = out["promise_tracker"]["rows"]
ok("4c: growth verdict computed in Python", rows[0]["verdict"] == "delivered" and rows[0]["delivered"] == "12.0% YoY", f"{rows[0]['verdict']} / {rows[0]['delivered']}")
ok("4c: absolute PAT verdict computed", rows[1]["verdict"] == "delivered" and rows[1]["delivered"] == "350.0 Rs Cr", f"{rows[1]['verdict']} / {rows[1]['delivered']}")
ok("4c: no-data quarter left to LLM verdict", rows[2]["verdict"] == "unverifiable")

print("\n-- 4b: citation validation --")
extractions = [{"doc": "Concall Aug 2026", "valid_pages": {1, 2, 3}}, {"doc": "Annual Report 2026", "valid_pages": {10, 11}}]
rep2 = {"sections": {
    "business_snapshot": {"title": "t", "text": "x", "citations": [{"doc": "Concall Aug 2026", "period": "", "page": 2}, {"doc": "Concall Aug 2026", "period": "", "page": 99}]},
}, "promise_tracker": {"rows": [
    {"promise": "good", "citations": [{"doc": "Annual Report 2026", "period": "", "page": 10}]},
    {"promise": "bad", "citations": [{"doc": "Imaginary doc", "period": "", "page": 1}]},
]}}
v2 = _validate_citations(rep2, extractions)
cits = v2["sections"]["business_snapshot"]["citations"]
ok("4b: invalid section citation dropped", len(cits) == 1 and cits[0]["page"] == 2)
ok("4b: row with valid citation kept", len(v2["promise_tracker"]["rows"]) == 1 and v2["promise_tracker"]["rows"][0]["promise"] == "good")
ok("4b: row with all-invalid citations dropped", all(r["promise"] != "bad" for r in v2["promise_tracker"]["rows"]))

print("\n" + ("ALL PASS" if all(c for _, c in PASS) else "SOME FAILED") + f" ({sum(c for _, c in PASS)}/{len(PASS)})")
