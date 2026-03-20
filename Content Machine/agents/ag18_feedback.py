"""AG·18 — Performance Feedback: Logs performance data and discovers winning patterns."""

import json
import os
from datetime import datetime
from shared_memory.memory import update_state, get_field, log_agent_completion, _load, _save

PERFORMANCE_FILE = "shared_memory/performance_log.json"


def _load_performance() -> dict:
    if os.path.exists(PERFORMANCE_FILE):
        with open(PERFORMANCE_FILE) as f:
            return json.load(f)
    return {}


def _save_performance(data: dict):
    os.makedirs("shared_memory", exist_ok=True)
    with open(PERFORMANCE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_performance(
    article_id: str,
    clicks: int = 0,
    impressions: int = 0,
    avg_position: float = 0.0,
    ctr: float = 0.0,
    ai_citations: int = 0,
    source: str = "manual",
) -> dict:
    """
    Log GSC performance data for a published article.
    Call this manually after pulling data from Google Search Console.

    ai_citations: how many times Perplexity/ChatGPT/Copilot cited this article.
    """
    keyword = get_field(article_id, "keyword")
    perf = _load_performance()

    if article_id not in perf:
        perf[article_id] = {"keyword": keyword, "history": []}

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "clicks": clicks,
        "impressions": impressions,
        "avg_position": round(avg_position, 1),
        "ctr_pct": round(ctr * 100, 2),
        "ai_citations": ai_citations,
        "source": source,
    }

    perf[article_id]["history"].append(entry)
    _save_performance(perf)

    print(f"[AG·18] Performance logged: '{keyword}' | Position: {avg_position} | Clicks: {clicks} | AI citations: {ai_citations}")
    return entry


def analyze_patterns() -> dict:
    """
    Analyzes all articles to find what structural/content patterns drive performance.
    Run this after 10+ articles are published and have data.
    """
    perf = _load_performance()
    data = _load()
    insights = {"analyzed_at": datetime.now().isoformat(), "patterns": [], "top_articles": [], "recommendations": []}

    scored = []
    for article_id, perf_data in perf.items():
        history = perf_data.get("history", [])
        if not history:
            continue
        latest = history[-1]
        state = data.get(article_id, {})
        quality_score = state.get("quality_result", {}).get("total", 0)
        entity_count = state.get("entity_audit", {}).get("total_count", 0)
        word_count = len(state.get("draft", "").split())

        scored.append({
            "article_id": article_id,
            "keyword": perf_data.get("keyword"),
            "avg_position": latest.get("avg_position", 99),
            "clicks": latest.get("clicks", 0),
            "ai_citations": latest.get("ai_citations", 0),
            "quality_score": quality_score,
            "entity_count": entity_count,
            "word_count": word_count,
        })

    scored.sort(key=lambda x: x["avg_position"])
    insights["top_articles"] = scored[:5]

    # Pattern analysis
    if len(scored) >= 5:
        top_half = scored[:len(scored)//2]
        bottom_half = scored[len(scored)//2:]

        avg_quality_top = sum(a["quality_score"] for a in top_half) / len(top_half) if top_half else 0
        avg_quality_bottom = sum(a["quality_score"] for a in bottom_half) / len(bottom_half) if bottom_half else 0

        if avg_quality_top > avg_quality_bottom:
            insights["patterns"].append(
                f"High quality gate scores correlate with better rankings "
                f"(top avg: {avg_quality_top:.0f} vs bottom avg: {avg_quality_bottom:.0f})"
            )

        # AI citation correlation
        cited = [a for a in scored if a["ai_citations"] > 0]
        if cited:
            avg_pos_cited = sum(a["avg_position"] for a in cited) / len(cited)
            insights["patterns"].append(
                f"Articles with AI citations avg position: {avg_pos_cited:.1f} "
                f"({len(cited)}/{len(scored)} articles cited by AI)"
            )

    # Recommendations based on performance gaps
    failing = [a for a in scored if a["avg_position"] > 20]
    for a in failing[:3]:
        insights["recommendations"].append(
            f"Update '{a['keyword']}' — position {a['avg_position']} — "
            f"quality score: {a['quality_score']}"
        )

    print(f"[AG·18] Pattern analysis: {len(scored)} articles | {len(insights['patterns'])} patterns found")
    return insights


def run(article_id: str) -> dict:
    """Initialize performance tracking for a newly published article."""
    keyword = get_field(article_id, "keyword")
    print(f"[AG·18] Performance tracking initialized: '{keyword}'")

    perf = _load_performance()
    perf[article_id] = {
        "keyword": keyword,
        "tracking_started": datetime.now().isoformat(),
        "history": [],
    }
    _save_performance(perf)

    result = {
        "tracking_active": True,
        "article_id": article_id,
        "keyword": keyword,
        "instructions": (
            "After publishing, use log_performance(article_id, clicks, impressions, "
            "avg_position, ctr, ai_citations) to add GSC data. "
            "Run analyze_patterns() after 10+ articles."
        ),
    }

    update_state(article_id, "performance_tracking", result)

    log_agent_completion(article_id, "AG·18", {
        "output_keys": ["performance_tracking"],
        "key_outputs": {"tracking_active": True},
        "metrics": {},
    })
    return result
