import json

import httpx

from . import db, llm
from .config import TAVILY_API_KEY


def extract_person_role(subject: str) -> dict | None:
    out = llm.call_json(
        "bio_person_extract",
        "From this Indian exchange announcement, extract the incoming person. Return STRICT JSON "
        '{"person": "name or null", "role": "role/title or null", "is_incoming": true|false}. '
        "is_incoming=false if the announcement is about someone leaving/retiring with no named successor.\n\n"
        + subject[:800],
        tier="cheap",
    )
    if out and out.get("person") and out.get("is_incoming", True):
        return {"person": out["person"], "role": out.get("role") or ""}
    return None


def tavily_search(query: str) -> list[dict]:
    if not TAVILY_API_KEY:
        return []
    try:
        r = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 5, "search_depth": "basic"},
            timeout=25,
        )
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []


def build_bio(subject: str) -> dict | None:
    who = extract_person_role(subject)
    if not who:
        return None
    query = f"{who['person']} {who['role']} appointment India background career".strip()
    results = tavily_search(query)
    if not results:
        return None
    content = "\n".join(f"- {r.get('title','')}: {r.get('content','')[:400]}" for r in results[:5])
    out = llm.call_json(
        "bio_summary",
        "Write a short professional bio (2-3 sentences, factual, neutral) of this person based ONLY on these search snippets. "
        'Return STRICT JSON: {"bio": "...", "source_query": "..."}\n'
        f"Person: {who['person']} | Role: {who['role']}\nSnippets:\n{content}",
        tier="cheap",
    )
    if not out or not out.get("bio"):
        return None
    return {"person": who["person"], "role": who["role"], "bio": out["bio"], "source_query": query}


def enrich_bios() -> int:
    n = 0
    with db.get_db() as conn:
        pending = conn.execute(
            """SELECT a.id, a.subject FROM announcements a
               LEFT JOIN renders r ON r.announcement_id = a.id AND r.kind = 'bio'
               WHERE a.category = 'management_change' AND r.id IS NULL
               ORDER BY a.priority DESC LIMIT 10"""
        ).fetchall()
    for row in pending:
        bio = build_bio(row["subject"] or "")
        if bio:
            with db.get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'bio', ?)",
                    (row["id"], json.dumps(bio)),
                )
            n += 1
        else:
            with db.get_db() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO renders (announcement_id, kind, payload_json) VALUES (?, 'bio', ?)",
                    (row["id"], json.dumps({"bio": None})),
                )
    return n
