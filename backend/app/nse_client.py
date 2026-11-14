import json
import random
import time

from curl_cffi import requests as cr

BASE = "https://www.nseindia.com"
ANN_URL = f"{BASE}/api/corporate-announcements"
REFERER = f"{BASE}/all-corporate-announcements"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


class NseError(RuntimeError):
    pass


def _new_session() -> cr.Session:
    s = cr.Session(impersonate="chrome124")
    s.headers.update({"Accept-Language": "en-US,en;q=0.9"})
    for warm in (BASE, REFERER):
        try:
            s.get(warm, timeout=20)
        except Exception:
            time.sleep(0.5 + random.random())
    return s


def _extract_rows(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "latestAnnouncements", "Table"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def fetch_announcements(days_back: int = 1) -> tuple[list[dict], str]:
    from datetime import date, timedelta

    today = date.today()
    frm = (today - timedelta(days=days_back)).strftime("%d-%m-%Y")
    to = today.strftime("%d-%m-%Y")
    attempts = [
        ("get-dates", lambda s: s.get(ANN_URL, params={"index": "equities", "from_date": frm, "to_date": to}, headers={"Referer": REFERER}, timeout=30)),
        ("get-plain", lambda s: s.get(ANN_URL, params={"index": "equities"}, headers={"Referer": REFERER}, timeout=30)),
        ("post-dates", lambda s: s.post(ANN_URL, json={"from_date": frm, "to_date": to, "index": "equities"}, headers={"Referer": REFERER}, timeout=30)),
    ]
    last_err = None
    for name, call in attempts:
        try:
            s = _new_session()
            r = call(s)
            if r.status_code != 200:
                last_err = f"{name}: HTTP {r.status_code}"
                continue
            rows = _extract_rows(r.json())
            if rows:
                return rows, name
            last_err = f"{name}: 200 but 0 rows"
        except Exception as e:
            last_err = f"{name}: {type(e).__name__}: {str(e)[:120]}"
        time.sleep(1)
    raise NseError(last_err or "all strategies failed")


def normalize(row: dict) -> dict | None:
    symbol = row.get("symbol") or row.get("sm_name") or row.get("smSymbol")
    if not symbol:
        return None
    headline = (row.get("desc") or row.get("subject") or "").strip()
    return {
        "ticker": symbol.upper(),
        "headline": headline,
        "nse_category": row.get("csvName") or row.get("category") or None,
        "subject": (row.get("attchmntText") or row.get("subject") or "").strip(),
        "pdf_url": row.get("attchmntFile") or None,
        "published_at": row.get("an_dt") or row.get("sort_date") or row.get("dt") or None,
        "raw": row,
    }


def download_pdf(url: str, dest_path) -> bool:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return True
    candidates = [url]
    if "bseindia.com/stockinfo/AnnPdfOpen.aspx" in url:
        candidates.append(url.split("Pname=")[-1].split("&")[0].replace(".pdf", ""))
    try:
        s = cr.Session(impersonate="chrome124")
        for i, u in enumerate(candidates):
            try:
                r = s.get(u, headers={"Referer": "https://www.bseindia.com/"} if "bseindia" in u else {"Referer": BASE}, timeout=45)
                if r.status_code == 200 and r.content[:5] == b"%PDF-":
                    dest_path.write_bytes(r.content)
                    return True
                if i == 0 and r.status_code in (301, 302, 303, 307):
                    loc = r.headers.get("location")
                    if loc:
                        candidates.append(loc)
            except Exception:
                continue
        return False
    except Exception:
        return False


def fetch_with_meta(days_back: int = 1):
    rows, strategy = fetch_announcements(days_back)
    out = [n for n in (normalize(r) for r in rows) if n]
    return out, strategy


if __name__ == "__main__":
    ann, strat = fetch_with_meta(2)
    print(json.dumps({"strategy": strat, "count": len(ann), "sample": ann[:2]}, indent=1)[:1500])
