# parser/full_article.py
import re, logging
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

log = logging.getLogger("runner")

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.9",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
    "Referer": "https://silkwayrally.com/",
}

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    retries = Retry(
        total=3, connect=3, read=3, backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def _needs_beget_cookie(html_snippet: str) -> bool:
    return "beget=begetok" in html_snippet

def _set_beget_cookie(sess: requests.Session, url: str):
    parsed = urlparse(url)
    domain = parsed.hostname
    if domain:
        sess.cookies.set("beget", "begetok", domain=domain, path="/")
        log.info(f"Set beget=begetok cookie for domain {domain}")

def _fetch_html(url: str) -> str:
    with _session() as s:
        r = s.get(url, timeout=20, allow_redirects=True)
        txt = r.text or ""
        ctype = r.headers.get("Content-Type", "")
        log.info(f"GET(article) {url} → {r.status_code} Content-Type={ctype}")
        if _needs_beget_cookie(txt[:400]):
            _set_beget_cookie(s, url)
            r2 = s.get(url, timeout=20, allow_redirects=True)
            txt = r2.text or ""
            ctype = r2.headers.get("Content-Type", "")
            log.info(f"RETRY(article) {url} → {r2.status_code} Content-Type={ctype}")
        return txt

CANDIDATE_SELECTORS = [
    # типовые WordPress-разметки
    "article .entry-content",
    ".entry-content",
    "article .post-content",
    ".post-content",
    'div[itemprop="articleBody"]',
    "article .content",
    "main article",
]

def extract_full_text(url: str) -> str:
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    node = None
    for sel in CANDIDATE_SELECTORS:
        node = soup.select_one(sel)
        if node:
            break
    if not node:
        node = soup.find("article") or soup.find("main") or soup.body

    # удалить мусор
    for t in node.select("script,style,noscript,form,aside,nav,footer,iframe"):
        t.decompose()

    # текст параграфами
    paras = [p.get_text(" ", strip=True) for p in node.select("p")
            if p.get_text(strip=True)]
    text = "\n\n".join(paras) if paras else (node.get_text(" ", strip=True) if node else "")

    # подчистим пробелы
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    return text
