# parser/rss_parser.py
import datetime as dt
from typing import List, Optional
from dataclasses import dataclass
import re
import logging
import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse

log = logging.getLogger("runner")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7",
    "Accept-Language": "ru,en;q=0.9",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
}

XML_DETECT_RE = re.compile(br"<\?xml|<rss\b|<feed\b", re.I)

@dataclass
class NewsItem:
    source_id: str
    title: str
    link: str
    summary: str
    published: Optional[str]  # ISO string
    guid: str

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def _is_xml(content: bytes) -> bool:
    head = content[:4096].strip()
    return bool(XML_DETECT_RE.search(head))

def _needs_beget_cookie(html_snippet: str) -> bool:
    return "beget=begetok" in html_snippet

def _set_beget_cookie(sess: requests.Session, url: str):
    parsed = urlparse(url)
    domain = parsed.hostname
    if not domain:
        return
    # Ставим куку на домен (обычно этого достаточно)
    sess.cookies.set("beget", "begetok", domain=domain, path="/")
    log.info(f"Set beget=begetok cookie for domain {domain}")

def _fetch_bytes(url: str) -> bytes:
    with _session() as s:
        # 1-й запрос
        r = s.get(url, timeout=20, allow_redirects=True, headers={"Referer": f"{urlparse(url).scheme}://{urlparse(url).hostname}/"})
        status = r.status_code
        ctype = r.headers.get("Content-Type", "")
        content = r.content or b""
        log.info(f"GET {url} → {status} Content-Type={ctype}")

        if _is_xml(content):
            return content

        # если HTML и видим намёк на Beget — ставим куку и ретраим
        preview = content[:200].decode("utf-8", errors="ignore")
        if _needs_beget_cookie(preview):
            _set_beget_cookie(s, url)
            r2 = s.get(url, timeout=20, allow_redirects=True, headers={"Referer": f"{urlparse(url).scheme}://{urlparse(url).hostname}/"})
            status2 = r2.status_code
            ctype2 = r2.headers.get("Content-Type", "")
            content2 = r2.content or b""
            log.info(f"RETRY with beget cookie {url} → {status2} Content-Type={ctype2}")
            if _is_xml(content2):
                return content2

        # не XML — залогируем сниппет и вернём как есть (дальше feedparser сам попробует)
        log.warning(f"Expected XML, got non-XML. Snippet: {preview!r}")
        return content

def _parse_feed(url: str):
    # Сначала пробуем «как есть» с заголовками
    fp = feedparser.parse(url, request_headers=DEFAULT_HEADERS)
    if fp.entries:
        return fp
    # Затем — качаем байты с нашей логикой (кука/ретраи) и парсим
    content = _fetch_bytes(url)
    return feedparser.parse(content)

def parse_datetime_struct(entry):
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        if getattr(entry, key, None):
            return dt.datetime(*getattr(entry, key)[:6], tzinfo=dt.timezone.utc)
    return None

def fetch_items(source_id: str, url: str, cap: int = 30) -> List[NewsItem]:
    fp = _parse_feed(url)

    if getattr(fp, "bozo", 0):
        log.warning(f"{source_id}: feedparser bozo_exception: {getattr(fp, 'bozo_exception', None)}")

    items: List[NewsItem] = []
    for e in fp.entries[:cap]:
        published_dt = parse_datetime_struct(e)
        published_iso = published_dt.isoformat() if published_dt else None
        guid = getattr(e, "id", None) or getattr(e, "guid", None) or getattr(e, "link", None) or (
            (getattr(e, "title", "") or "") + "|" + (getattr(e, "link", "") or "")
        )
        items.append(NewsItem(
            source_id=source_id,
            title=(getattr(e, "title", "(no title)") or "").strip(),
            link=(getattr(e, "link", "") or "").strip(),
            summary=(getattr(e, "summary", "") or getattr(e, "description", "") or ""),
            published=published_iso,
            guid=str(guid),
        ))

    log.info(f"{source_id}: parsed entries={len(items)}")
    return items
