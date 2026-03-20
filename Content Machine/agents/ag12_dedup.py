"""AG·12 — Content Dedup Guard: Checks cosine similarity + Sapling AI for AI content detection."""

import json
import math
import re
from shared_memory.memory import update_state, get_field, log_agent_completion, list_all_articles, _load
from tools.sapling_tool import check_ai_content


def _tokenize(text: str) -> dict:
    """Build word frequency vector (with basic stopword removal)."""
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
                 "of", "is", "it", "this", "that", "with", "be", "are", "was", "were"}
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    freq = {}
    for w in words:
        if w not in stopwords:
            freq[w] = freq.get(w, 0) + 1
    return freq


def _cosine_similarity(vec1: dict, vec2: dict) -> float:
    """Calculate cosine similarity between two word frequency vectors."""
    common = set(vec1.keys()) & set(vec2.keys())
    if not common:
        return 0.0
    dot = sum(vec1[w] * vec2[w] for w in common)
    mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def _check_originality_ai(text: str) -> dict:
    """Check AI content detection via Sapling AI (free replacement for Originality.ai)."""
    result = check_ai_content(text)
    # Normalize to expected format
    return {
        "skipped": result.get("skipped", False),
        "original_score": result.get("score"),   # 0-100, higher = more human
        "ai_score": result.get("ai_probability"),
        "passes": result.get("passes", True),
        "reason": result.get("reason", ""),
    }


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")

    print(f"[AG·12] Dedup check: '{keyword}'")

    current_vec = _tokenize(draft)
    all_articles = list_all_articles()
    data = _load()

    # Cosine similarity against all published articles
    similarities = []
    for article in all_articles:
        other_id = article["id"]
        if other_id == article_id:
            continue
        other_draft = data.get(other_id, {}).get("draft", "")
        other_keyword = data.get(other_id, {}).get("keyword", "")
        if not other_draft:
            continue
        other_vec = _tokenize(other_draft)
        sim = _cosine_similarity(current_vec, other_vec)
        if sim > 0.30:
            similarities.append({
                "article_id": other_id,
                "keyword": other_keyword,
                "similarity_pct": round(sim * 100, 1),
            })

    similarities.sort(key=lambda x: x["similarity_pct"], reverse=True)

    # Keyword cannibalization check
    keyword_conflicts = [
        a for a in all_articles
        if a["id"] != article_id
        and a.get("keyword", "").lower() == keyword.lower()
    ]

    # Originality.ai check
    originality_result = _check_originality_ai(draft)
    orig_status = "skipped" if originality_result.get("skipped") else f"{originality_result.get('original_score', '?')}% original"
    print(f"[AG·12] AI check: {orig_status}")

    max_sim = similarities[0]["similarity_pct"] if similarities else 0
    is_duplicate = max_sim > 85
    passes_originality = originality_result.get("passes", True)  # Default True if skipped

    result = {
        "similar_articles": similarities[:5],
        "max_similarity_pct": max_sim,
        "keyword_conflicts": keyword_conflicts,
        "originality_check": originality_result,
        "is_duplicate": is_duplicate,
        "has_cannibalization": bool(keyword_conflicts),
        "safe_to_publish": not is_duplicate and passes_originality,
    }

    update_state(article_id, "dedup_check", result)
    update_state(article_id, "status", "dedup_done")

    warnings = []
    if is_duplicate:
        warnings.append(f"HIGH SIMILARITY: {max_sim}% match with '{similarities[0]['keyword']}'")
    if keyword_conflicts:
        warnings.append(f"CANNIBALIZATION: keyword '{keyword}' already exists")
    if not passes_originality and not originality_result.get("skipped"):
        warnings.append(f"Originality.ai score low: {originality_result.get('original_score')}%")

    log_agent_completion(article_id, "AG·12", {
        "output_keys": ["dedup_check"],
        "key_outputs": {
            "max_similarity": max_sim,
            "safe_to_publish": result["safe_to_publish"],
            "originality_score": originality_result.get("original_score"),
        },
        "metrics": {"max_similarity_pct": max_sim},
        "warnings": warnings,
    })

    status = "✅ SAFE" if result["safe_to_publish"] else "❌ DUPLICATE RISK"
    print(f"[AG·12] {status} | Max similarity: {max_sim}%")
    return result
