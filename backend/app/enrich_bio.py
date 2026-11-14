import json
from pathlib import Path

import httpx

from . import db, llm, nse_client
from .config import BACKEND_DIR, TAVILY_API_KEY

FILINGS_DIR = BACKEND_DIR / "data" / "filings"
NO_PROFILE = "No reliable public profile found"


def _filing_text(pdf_url: str, ticker: str, max_pages: int = 2) -> str:
    dest = FILINGS_DIR / ticker / (pdf_url.split("/")[-1].split("?")[0] or "ann.pdf")
    if not nse_client.download_pdf(pdf_url, dest):
        return ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(dest))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    except Exception:
        return ""


def extract_person(ticker: str, subject: str, pdf_url: str | None) -> dict | None:
    filing_text = ""
    if pdf_url:
        filing_text = _filing_text(pdf_url, ticker)[:6000]
    prompt = (
        "This is an Indian corporate announcement about a management change, plus (if available) the first pages of the filing PDF.\n"
        f"TICKER: {ticker}\nSUBJECT: {subject[:500]}\nFILING TEXT:\n{filing_text or '(no filing text)'}\n\n"
        'Return STRICT JSON: {"person": "full name or null", "role": "new role or null", '
        '"is_incoming": true|false, "bio_in_filing": "1-3 sentence bio if the filing itself describes the person\'s '
        'background (verbatim or tight summary), else null", "company_name": "company name or null"}\n'
        "Rules: extract the INCOMING person only. If the filing gives their age/experience/past roles, that is the bio_in_filing. "
        "No guessing — use only what is written."
    )
    out = llm.call_json("bio_person_extract", prompt, tier="cheap")
    if out and out.get("person") and out.get("is_incoming", True):
        return out
    return None


def tavily_search(query: str) -> list[dict]:
    if not TAVILY_API_KEY:
        return []
    try:
        r = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 6, "search_depth": "basic"},
            timeout=25,
        )
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []


def _snippets_match_company(results: list[dict], ticker: str, company: str | None) -> bool:
    names = [ticker.lower()]
    if company:
        words = [w for w in re_split_company(company) if len(w) > 2]
        names.append(" ".join(words).lower())
    for r in results:
        blob = (r.get("title", "") + " " + r.get("content", "") + " " + r.get("url", "")).lower()
        if any(n in blob for n in names):
            return True
    return False


def re_split_company(company: str) -> list[str]:
    return company.replace("Limited", " ").replace("Ltd", " ").replace("Pvt", " ").split()


def build_bio(ticker: str, subject: str, pdf_url: str | None) -> dict:
    who = extract_person(ticker, subject, pdf_url)
    if not who:
        return {"bio": None}
    person, role = who["person"], who.get("role") or ""
    company = who.get("company_name") or ticker
    if who.get("bio_in_filing"):
        return {
            "person": person, "role": role, "bio": who["bio_in_filing"],
            "sources": [f"{pdf_url}#page=1"] if pdf_url else [],
            "source_type": "filing",
        }
    query = f"{person} {company} {role}".strip()
    results = tavily_search(query)
    if not results or not _snippets_match_company(results, ticker, company):
        return {"person": person, "role": role, "bio": NO_PROFILE, "sources": [], "source_type": "none"}
    snippets = "\n".join(f"- {r.get('title','')}: {r.get('content','')[:350]} [{r.get('url','')}]" for r in results[:5])
    out = llm.call_json(
        "bio_summary",
        "Write a short professional bio (2-3 sentences, factual, neutral) based ONLY on these snippets. "
        'If the snippets do not clearly describe THIS person at THIS company, reply bio = "No reliable public profile found". '
        'Return STRICT JSON: {"bio": "..."}\n'
        f"Person: {person} | Role: {role} | Company: {company}\nSnippets:\n{snippets}",
        tier="cheap",
    )
    bio = (out or {}).get("bio") or NO_PROFILE
    if "No reliable" in bio:
        return {"person": person, "role": role, "bio": NO_PROFILE, "sources": [], "source_type": "none"}
    return {
        "person": person, "role": role, "bio": bio, "source_query": query,
        "sources": [r.get("url") for r in results[:5] if r.get("url")],
        "source_type": "web",
    }


def enrich_bios() -> int:
    n = 0
    with db.get_db() as conn:
        pending = conn.execute(
            """SELECT a.id, a.ticker, a.subject, a.pdf_url FROM announcements a
               LEFT JOIN renders r ON r.announcement_id = a.id AND r.kind = 'bio'
               WHERE a.category = 'management_change' AND r.id IS NULL
               ORDER BY a.priority DESC LIMIT 10"""
        ).fetchall()
    for row in pending:
        bio = build_bio(row["ticker"], row["subject"] or "", row["pdf_url"])
        with db.get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'bio', ?)",
                (row["id"], json.dumps(bio)),
            )
        n += 1
    return n
