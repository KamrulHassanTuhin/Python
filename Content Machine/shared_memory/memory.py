"""
Shared Memory Layer — Foundation for all 21 agents.
All agents read from and write to this module.
Uses a local JSON file (no external DB required).
"""

import json
import os
from datetime import datetime

MEMORY_FILE = "shared_memory/state.json"


def _load() -> dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(data: dict):
    os.makedirs("shared_memory", exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────
# CORE STATE MANAGEMENT
# ─────────────────────────────────────────────────────────────────

def init_article(keyword: str, niche: str = "general") -> str:
    """Initialize state for a new article. Returns unique article_id."""
    data = _load()
    article_id = f"{keyword.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    data[article_id] = {
        "keyword": keyword,
        "niche": niche,
        "status": "initialized",
        "created_at": datetime.now().isoformat(),
        # Pipeline artifacts
        "subqueries": [],
        "research": {},
        "outline": {},
        "draft": "",
        "scores": {},
        "voice_profile": {},
        "schema": {},
        "schema_html": "",
        "media_plan": {},
        "internal_links": {},
        "freshness_schedule": {},
        "quality_result": {},
        "distribution": {},
        "published": False,
        # Inter-agent communication log
        "agent_log": [],
        # Saved experience bullets (persists across retries)
        "experience_bullets": [],
    }
    _save(data)
    return article_id


def update_state(article_id: str, key: str, value):
    """Update any field in the article state."""
    data = _load()
    if article_id not in data:
        raise KeyError(f"Article ID '{article_id}' not found in memory.")
    data[article_id][key] = value
    data[article_id]["updated_at"] = datetime.now().isoformat()
    _save(data)


def get_state(article_id: str) -> dict:
    """Read the full state of an article."""
    data = _load()
    if article_id not in data:
        raise KeyError(f"Article ID '{article_id}' not found in memory.")
    return data[article_id]


def get_field(article_id: str, key: str):
    """Read a specific field from the article state."""
    return get_state(article_id).get(key)


def save_published(article_id: str, output_path: str, score: float):
    """Mark article as published and log it."""
    data = _load()
    if article_id in data:
        data[article_id]["published"] = True
        data[article_id]["output_path"] = output_path
        data[article_id]["final_score"] = score
        data[article_id]["published_at"] = datetime.now().isoformat()
    _save(data)


def list_all_articles() -> list:
    """Return a summary list of all articles."""
    data = _load()
    return [
        {
            "id": aid,
            "keyword": v.get("keyword"),
            "status": v.get("status"),
            "score": v.get("final_score"),
            "published": v.get("published"),
        }
        for aid, v in data.items()
        if not aid.startswith("_")
    ]


# ─────────────────────────────────────────────────────────────────
# INTER-AGENT COMMUNICATION
# ─────────────────────────────────────────────────────────────────

def log_agent_completion(article_id: str, agent_id: str, summary: dict):
    """
    Each agent calls this at completion to log what it produced.
    The next agent reads this log to understand pipeline history.

    summary should include:
        - 'output_keys': list of state keys this agent wrote
        - 'key_outputs': dict of important values (not full drafts)
        - 'warnings': list of any issues found
        - 'metrics': dict of measurable results
    """
    data = _load()
    if article_id not in data:
        return

    entry = {
        "agent": agent_id,
        "timestamp": datetime.now().isoformat(),
        "output_keys": summary.get("output_keys", []),
        "key_outputs": summary.get("key_outputs", {}),
        "warnings": summary.get("warnings", []),
        "metrics": summary.get("metrics", {}),
    }

    if "agent_log" not in data[article_id]:
        data[article_id]["agent_log"] = []

    data[article_id]["agent_log"].append(entry)
    _save(data)


def get_agent_log(article_id: str) -> list:
    """Read the full agent execution log for an article."""
    return get_field(article_id, "agent_log") or []


def get_last_agent_output(article_id: str, agent_id: str) -> dict:
    """Get the most recent log entry for a specific agent."""
    log = get_agent_log(article_id)
    matches = [e for e in log if e.get("agent") == agent_id]
    return matches[-1] if matches else {}


def get_pipeline_summary(article_id: str) -> dict:
    """
    Returns a compact summary of what each agent produced.
    Next agent reads this to understand full pipeline context.
    """
    log = get_agent_log(article_id)
    state = get_state(article_id)

    return {
        "keyword": state.get("keyword"),
        "niche": state.get("niche"),
        "current_status": state.get("status"),
        "agents_completed": [e["agent"] for e in log],
        "word_count": len(state.get("draft", "").split()),
        "entity_count": state.get("entity_audit", {}).get("total_count", 0),
        "subquery_count": len(state.get("subqueries", [])),
        "quality_score": state.get("quality_result", {}).get("total", 0),
        "dedup_safe": state.get("dedup_check", {}).get("safe_to_publish", True),
        "warnings": [w for e in log for w in e.get("warnings", [])],
    }
