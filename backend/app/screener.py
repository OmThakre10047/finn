import re
import time

from curl_cffi import requests as cr

BASE = "https://www.screener.in"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_slug_cache: dict[str, str] = {}


def _slug(ticker: str) -> str:
    if ticker in _slug_cache:
        return _slug_cache[ticker]
    s = cr.Session(impersonate="chrome124")
    r = s.get(f"{BASE}/company/{ticker}/consolidated/", headers={"User-Agent": UA}, timeout=30)
    if r.status_code == 200:
        _slug_cache[ticker] = ticker
        return ticker
    r2 = s.get(f"{BASE}/company/{ticker}/", headers={"User-Agent": UA}, timeout=30)
    if r2.status_code == 200:
        _slug_cache[ticker] = ticker
        return ticker
    raise RuntimeError(f"screener page not found for {ticker} (HTTP {r.status_code}/{r2.status_code})")


def fetch_company_html(ticker: str) -> str:
    slug = _slug(ticker)
    s = cr.Session(impersonate="chrome124")
    r = s.get(f"{BASE}/company/{slug}/consolidated/", headers={"User-Agent": UA}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"screener HTTP {r.status_code} for {ticker}")
    return r.text


def parse_documents(html: str) -> dict:
    """Extract concall transcripts + annual reports from screener's documents blocks."""
    docs = {"annual_reports": [], "concalls": [], "results": []}
    for m in re.finditer(r'<div class="documents ([a-z\- ]+?)[ ]*flex-column"(.*?)(?=<div class="documents |<div id=|</section|$)', html, re.S):
        kind, block = m.group(1), m.group(2)
        for li in re.finditer(r'<li[^>]*>(.*?)</li>', block, re.S):
            item = li.group(1)
            period_m = re.search(r'font-weight-500[^"]*"[^>]*>\s*([A-Za-z]{3} \d{4}|\d{4})\s*<', item)
            period = period_m.group(1) if period_m else ""
            for a in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]*)</a>', item):
                url, label = a.group(1), a.group(2).strip()
                bare = url.split("#")[0].lower()
                if ".pdf" not in bare:
                    continue
                if "concalls" in kind:
                    docs["concalls"].append({"url": url, "period": period, "label": label or "Transcript"})
                elif "annual" in kind:
                    docs["annual_reports"].append({"url": url, "period": period, "label": label})
    seen = set()
    for k in docs:
        uniq = []
        for d in docs[k]:
            if d["url"] not in seen:
                seen.add(d["url"])
                uniq.append(d)
        docs[k] = uniq
    return docs


def parse_quarterly_table(html: str) -> dict:
    """Parse screener's Quarterly table (10 quarters) → {periods: [...], rows: {metric: [values]}}."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    out = {}
    for table in soup.find_all("table"):
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        if not any("Sep 2026" in h or "Jun 2026" in h or "Sep 2025" in h for h in headers):
            continue
        body_headers = [h for h in headers if h and not h.isalpha() or " 20" in h]
        periods = [h for h in headers if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}$", h)]
        if not periods:
            continue
        rows = {}
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            name = tds[0].get_text(" ", strip=True)
            vals = [td.get_text(" ", strip=True).replace(",", "") for td in tds[1:]]
            rows[name] = vals
        out["periods"] = periods
        out["rows"] = rows
        break
    return out


def parse_snapshot_metrics(html: str) -> dict:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    top = {}
    for li in soup.select("ul#top-ratios li"):
        name_el = li.find("span", class_="name")
        num_el = li.find("span", class_="number")
        if name_el and num_el:
            top[name_el.get_text(strip=True)] = num_el.get_text(strip=True)
    return top


def fetch_all(ticker: str) -> dict:
    html = fetch_company_html(ticker)
    time.sleep(0.3)
    return {
        "ticker": ticker,
        "documents": parse_documents(html),
        "quarterly": parse_quarterly_table(html),
        "top_ratios": parse_snapshot_metrics(html),
    }
