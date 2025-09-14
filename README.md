# RallyDriftWorld RSS Bot

Hourly GitHub Actions job that:
- fetches news from RSS feeds (Silk Way Rally, VDrifte),
- de-duplicates via a repo-persisted state file,
- posts fresh items to a Telegram channel,
- saves logs (committed + uploaded as workflow artifact),
- designed to be extended with Selenium-based parsers for non-RSS sources.

## Quick start

1. **Create a repo** and push these files.
2. In GitHub → *Settings* → *Secrets and variables* → *Actions*, add:
   - `TELEGRAM_BOT_TOKEN` — your bot token from @BotFather
   - `TELEGRAM_CHAT_ID` — your channel ID (e.g., `-1001234567890`), or a user/group id for testing.
3. Adjust `config.yaml` if needed (sources, item caps, per-run max posts).
4. The workflow is scheduled hourly, or run it manually in *Actions* → **Run workflow**.

## Local run

```bash
python -m venv .venv && . .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Extending (non-RSS sources)

Add a new parser module (e.g., `parser/selenium_source.py`) that implements `fetch_items()` returning a list of `NewsItem`. Register it in `main.py` (see `get_all_sources()`).
