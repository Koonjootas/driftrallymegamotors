import asyncio, os, html
from typing import List
from dataclasses import dataclass
from telegram import Bot

@dataclass
class OutMsg:
    text: str
    disable_web_page_preview: bool = False

import re, html as _html

def _clean_summary(summary: str) -> str:
    if not summary:
        return ""
    # Сначала переводы строк для <br> и </p>
    summary = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", summary)
    summary = re.sub(r"(?i)</\s*p\s*>", "\n\n", summary)
    # Удаляем все остальные теги (оставляем чистый текст)
    summary = re.sub(r"<[^>]+>", "", summary)
    # Декодируем HTML-сущности (&nbsp; &amp; и т.д.)
    summary = _html.unescape(summary)
    # Чистим лишние пробелы
    summary = re.sub(r"[ \t]+\n", "\n", summary).strip()
    return summary

def make_html_message(title: str, link: str, summary: str) -> str:
    title_html = _html.escape(title)
    summary_clean = _clean_summary(summary or "")
    if len(summary_clean) > 200:
        summary_clean = summary_clean[:200].rsplit(" ", 1)[0] + "…"
    return f"<b>{title_html}</b>\n\n{_html.escape(summary_clean)}\n\n<a href=\"{_html.escape(link)}\">Читать полностью</a>"


async def post_messages(msgs: List[OutMsg]):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
    bot = Bot(token=token)
    for m in msgs:
        await bot.send_message(chat_id=chat_id, text=m.text, parse_mode="HTML", disable_web_page_preview=m.disable_web_page_preview)
        await asyncio.sleep(1.2)  # be gentle
