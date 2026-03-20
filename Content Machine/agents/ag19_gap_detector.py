"""AG·19 — Content Gap Detector: Finds missed topics, position 8-20 quick wins, new keyword opportunities."""

import anthropic
import json
import os
from config import ANTHROPIC_API_KEY
from tools.json_helper import extract_json
from shared_memory.memory import _load, _save
from tools.serper_tool import google_search
from datetime import datetime

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

GAP_QUEUE_FILE = "shared_memory/keyword_queue.json"


def _load_queue() -> list:
    if os.path.exists(GAP_QUEUE_FILE):
        with open(GAP_QUEUE_FILE) as f:
            return json.load(f)
    return []


def _save_queue(queue: list):
    os.makedirs("shared_memory", exist_ok=True)
    with open(GAP_QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)


def find_gaps(niche: str, existing_keywords: list[str]) -> dict:
    """Discover content gaps in a niche based on search data and competitor analysis."""
    print(f"[AG·19] Gap detection for niche: '{niche}'")

    # Search for recent content in the niche
    search_results = google_search(f"best {niche} guides 2025 2026", num=10)
    organic = search_results.get("organic", [])
    paa = search_results.get("peopleAlsoAsk", [])

    paa_questions = [item.get("question", "") for item in paa]
    competitor_titles = [r.get("title", "") for r in organic[:8]]

    # Filter PAA questions not already covered
    uncovered_paa = [q for q in paa_questions if not any(
        kw.lower() in q.lower() for kw in existing_keywords
    )]

    prompt = f"""
You are a content gap analyst for a "{niche}" niche website.

EXISTING KEYWORDS COVERED: {json.dumps(existing_keywords[:25])}
UNCOVERED PAA QUESTIONS: {json.dumps(uncovered_paa)}
COMPETITOR RECENT ARTICLES: {json.dumps(competitor_titles)}

Identify valuable content gaps. Be specific about keyword opportunities.

Return JSON:
{{
    "high_priority_gaps": [
        {{
            "keyword": "exact target keyword phrase",
            "search_intent": "informational|commercial|transactional|navigational",
            "estimated_difficulty": "low|medium|high",
            "content_type": "guide|comparison|listicle|tutorial|review",
            "why_gap": "specific reason this is underserved"
        }}
    ],
    "quick_wins": [
        {{
            "keyword": "keyword likely ranking position 8-20",
            "why_quick_win": "why this can be improved quickly",
            "action": "update|expand|optimize"
        }}
    ],
    "topical_cluster_gaps": ["missing cluster topic 1", "missing cluster topic 2"],
    "competitor_only_topics": ["topic competitor ranks for that you don't"]
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    gaps = extract_json(raw, default={"high_priority_gaps": [], "quick_wins": []})

    # Add high-priority gaps to keyword queue
    queue = _load_queue()
    existing_in_queue = {item.get("keyword", "").lower() for item in queue}

    added = 0
    for gap in gaps.get("high_priority_gaps", [])[:5]:
        kw = gap.get("keyword", "")
        if kw and kw.lower() not in existing_in_queue and kw not in existing_keywords:
            queue.append({
                "keyword": kw,
                "niche": niche,
                "source": "gap_detector",
                "priority": "high",
                "content_type": gap.get("content_type", "guide"),
                "difficulty": gap.get("estimated_difficulty", "medium"),
                "added_at": datetime.now().isoformat(),
            })
            added += 1

    for win in gaps.get("quick_wins", [])[:3]:
        kw = win.get("keyword", "")
        if kw and kw.lower() not in existing_in_queue and kw not in existing_keywords:
            queue.append({
                "keyword": kw,
                "niche": niche,
                "source": "quick_win",
                "priority": "medium",
                "action": win.get("action", "update"),
                "added_at": datetime.now().isoformat(),
            })
            added += 1

    _save_queue(queue)

    gaps["added_to_queue"] = added
    gaps["queue_total"] = len(queue)
    gaps["detected_at"] = datetime.now().isoformat()

    print(f"[AG·19] Gaps found: {len(gaps.get('high_priority_gaps', []))} | Quick wins: {len(gaps.get('quick_wins', []))} | Queue: {len(queue)}")
    return gaps


def get_next_keyword() -> dict | None:
    """Pop the highest-priority keyword from the queue."""
    queue = _load_queue()
    if not queue:
        print("[AG·19] Keyword queue is empty.")
        return None

    # Sort: high priority first, then oldest added
    queue.sort(key=lambda x: (0 if x.get("priority") == "high" else 1, x.get("added_at", "")))
    next_kw = queue.pop(0)
    _save_queue(queue)
    print(f"[AG·19] Next keyword from queue: '{next_kw.get('keyword')}'")
    return next_kw


def view_queue() -> list:
    """View all keywords in the queue without removing any."""
    queue = _load_queue()
    print(f"[AG·19] Keyword queue: {len(queue)} items")
    for i, item in enumerate(queue, 1):
        print(f"  {i}. [{item.get('priority')}] {item.get('keyword')} ({item.get('content_type', 'guide')})")
    return queue
