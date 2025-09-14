import asyncio
import os
from typing import List
from dataclasses import dataclass

import yaml

from utils.logging import setup_logger
from storage.state import load_state, save_state, prune_old, is_seen, mark_seen
from parser.rss_parser import fetch_items, NewsItem
from parser.full_article import extract_full_text
from poster.telegram_poster import make_html_message, post_messages, OutMsg


@dataclass
class Source:
    id: str
    type: str
    url: str
    enabled: bool
    expand_full_article: bool = False


def get_all_sources(cfg) -> List[Source]:
    res: List[Source] = []
    for s in cfg.get("sources", []):
        if not s.get("enabled", True):
            continue
        res.append(
            Source(
                id=s["id"],
                type=s["type"],
                url=s["url"],
                enabled=True,
                expand_full_article=bool(s.get("expand_full_article", False)),
            )
        )
    return res


def format_item(cfg, item: NewsItem) -> OutMsg:
    fmt = cfg.get("post_format", "html")
    if fmt == "html":
        return OutMsg(
            text=make_html_message(item.title, item.link, item.summary),
            disable_web_page_preview=False,
        )
    else:
        text = f"*{item.title}*\n\n{item.summary}\n\n[Читать полностью]({item.link})"
        return OutMsg(text=text, disable_web_page_preview=False)


async def run():
    log, logfile = setup_logger()
    log.info("Start run")
    log.info(f"CWD: {os.getcwd()}")

    # Load config
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Load state & prune
    state = load_state()
    prune_old(state, cfg.get("dedupe_window_days", 21))
    save_state(state)

    # Sources
    sources = get_all_sources(cfg)
    log.info(f"Loaded sources: {len(sources)}")
    for s in sources:
        log.info(
            f"source -> id={s.id} type={s.type} enabled={s.enabled} "
            f"url={s.url} expand_full={getattr(s, 'expand_full_article', False)}"
        )

    cap = int(cfg.get("max_items_per_source", 30))
    max_posts = int(cfg.get("max_posts_per_run", 12))

    # Collect items
    pending: List[NewsItem] = []
    for idx, src in enumerate(sources, 1):
        t = (src.type or "").strip().lower()
        log.info(f"[{idx}/{len(sources)}] BEGIN {src.id} (type={t})")

        items: List[NewsItem] = []

        if t in ("rss", "atom", "rss2", "rdf"):
            log.info(f"Fetching RSS: {src.id} {src.url}")
            items = fetch_items(src.id, src.url, cap=cap)

            # Expand to full article if enabled
            if getattr(src, "expand_full_article", False):
                for it in items:
                    try:
                        full_text = extract_full_text(it.link)
                        if full_text:
                            # keep safe under Telegram message limits
                            it.summary = (
                                full_text[:3500].rsplit(" ", 1)[0] + "…"
                                if len(full_text) > 3500
                                else full_text
                            )
                    except Exception as e:
                        log.warning(f"{src.id}: full article failed for {it.link}: {e}")

        elif t == "selenium":
            log.info(f"Fetching Selenium: {src.id} {src.url}")
            # TODO: plug your selenium parser here when ready
            items = []

        else:
            log.warning(f"Unknown source type: {src.type!r}, skipping.")
            items = []

        # Dedupe
        fresh = [it for it in items if not is_seen(state, src.id, it.guid)]
        log.info(f"{src.id}: {len(items)} items, {len(fresh)} fresh")
        pending.extend(fresh)

    # Sort by published (oldest first), fallback to title
    pending.sort(key=lambda x: (x.published or "", x.title))

    # Limit per run
    to_post = pending[:max_posts]
    log.info(f"Will post {len(to_post)} items")

    # Build messages
    out_msgs: List[OutMsg] = [format_item(cfg, it) for it in to_post]

    # Post
    if out_msgs:
        await post_messages(out_msgs)
        log.info("Posted messages")

    # Mark seen (only what we posted)
    for it in to_post:
        mark_seen(
            state,
            it.source_id,
            it.guid,
            it.published or "1970-01-01T00:00:00+00:00",
        )
    log.info("Updated state")

    log.info(f"Log saved to {logfile}")
    log.info("Done")


if __name__ == "__main__":
    asyncio.run(run())
