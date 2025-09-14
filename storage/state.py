import json, os, datetime as dt
from typing import Dict, Set

STATE_PATH = "storage/news_state.json"

def _now_utc():
    return dt.datetime.now(dt.timezone.utc)

def load_state() -> Dict:
    if not os.path.exists(STATE_PATH):
        return {"seen": {}, "last_run": None}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: Dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    state["last_run"] = _now_utc().isoformat()
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def prune_old(state: Dict, days: int):
    cutoff = _now_utc() - dt.timedelta(days=days)
    for src, entries in list(state.get("seen", {}).items()):
        pruned = {k: v for k, v in entries.items() if dt.datetime.fromisoformat(v) >= cutoff}
        state["seen"][src] = pruned

def is_seen(state: Dict, source_id: str, guid: str) -> bool:
    return guid in state.get("seen", {}).get(source_id, {})

def mark_seen(state: Dict, source_id: str, guid: str, when_iso: str):
    state.setdefault("seen", {}).setdefault(source_id, {})[guid] = when_iso
    save_state(state)
