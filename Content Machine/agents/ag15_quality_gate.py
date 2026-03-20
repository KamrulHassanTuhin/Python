"""AG·15 — Quality Gate: Scores article across 5 dimensions. PASS ≥85 | FLAG 70-84 | FAIL <70."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion, get_pipeline_summary
from tools.json_helper import extract_json
from prompts.sop_prompts import QUALITY_GATE_SOP
from datetime import datetime

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

BANNED_WORDS = [
    "delve", "tapestry", "vibrant", "foster", "leverage", "utilize",
    "furthermore", "moreover", "in conclusion", "it's worth noting",
    "it is important to note", "in today's world", "game-changer",
    "revolutionize", "groundbreaking", "cutting-edge", "seamlessly",
]


def _check_banned_words(draft: str) -> list[str]:
    lower = draft.lower()
    return [w for w in BANNED_WORDS if w in lower]


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    research = get_field(article_id, "research") or {}
    subqueries = get_field(article_id, "subqueries") or []
    schema = get_field(article_id, "schema") or {}
    entity_audit = get_field(article_id, "entity_audit") or {}
    dedup_check = get_field(article_id, "dedup_check") or {}
    technical_audit = get_field(article_id, "technical_audit") or {}
    voice_check = get_field(article_id, "voice_check") or {}
    pipeline = get_pipeline_summary(article_id)

    current_year = datetime.now().year
    print(f"[AG·15] Quality gate: '{keyword}'")

    # Pre-computed checks (from previous agents — inter-agent handoff)
    banned_found = _check_banned_words(draft)
    entity_count = entity_audit.get("total_count", 0)
    tech_score = technical_audit.get("overall_score", 0)
    word_count = len(draft.split())
    has_schema = bool(schema)
    has_faq = "## faq" in draft.lower() or "## frequently" in draft.lower()
    has_tldr = "tl;dr" in draft.lower()
    has_freshness = "last updated" in draft.lower() or "as of" in draft.lower()

    # CRITICAL: Read dedup result — if duplicate, auto-FAIL
    is_duplicate = dedup_check.get("is_duplicate", False)
    has_cannibalization = dedup_check.get("has_cannibalization", False)

    # Voice consistency
    voice_score = voice_check.get("score", 75)
    voice_consistent = voice_check.get("consistent", True)

    # Warnings from all previous agents
    all_warnings = pipeline.get("warnings", [])

    prompt = f"""
{QUALITY_GATE_SOP}

KEYWORD: "{keyword}"
WORD COUNT: {word_count}
ENTITY COUNT: {entity_count} (minimum 15 required)
HAS SCHEMA: {has_schema} | Schema types: {list(schema.keys())}
HAS FAQ: {has_faq}
HAS TLDR: {has_tldr}
HAS FRESHNESS SIGNALS: {has_freshness}
SUB-QUERIES AVAILABLE: {len(subqueries)}
TECHNICAL SCORE FROM AG10: {tech_score}/100
VOICE CONSISTENCY SCORE: {voice_score}/100
BANNED WORDS FOUND: {banned_found}
PIPELINE WARNINGS: {all_warnings[:5]}

ARTICLE (first 3000 chars):
{draft[:3000]}

ARTICLE (last 800 chars):
{draft[-800:]}

Score each dimension (0-20):
1. SEO Score (20): keyword in H1 (+5), correct H-tag hierarchy (+5), word count 2500+ (+5), meta description ready (+5)
2. GEO Score (20): direct answer in first 200 words (+5), FAQ present with exact query wording (+5), citation patterns "According to..." (+5), freshness "Last updated" or "As of" (+5)
3. Fan-out Coverage (20): 90%+ sub-queries answered = 20, 70%+ = 15, 50%+ = 10, <50% = 5
4. Technical (20): schema present (+5), ≥15 entities (+5), no banned words (+5), freshness signals (+5)
5. Freshness (20): statistics with years (+5), "Last updated" date (+5), temporal markers "As of {current_year}" (+5), no future dates (+5)

VOICE BONUS: if voice_score ≥ 90 → +10, ≥75 → +7, ≥60 → +4, else 0

Return ONLY this JSON:
{{
    "scores": {{
        "seo": 0,
        "geo": 0,
        "fanout": 0,
        "technical": 0,
        "freshness": 0,
        "voice_bonus": 0
    }},
    "total": 0,
    "verdict": "PASS",
    "issues": ["specific issue with point value"],
    "quick_fixes": ["exact action to fix each issue — one sentence each"]
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    result = extract_json(raw, default={"scores": {}, "total": 70, "verdict": "FLAG", "issues": [], "quick_fixes": []})

    # Apply penalties from pre-computed checks
    issues = result.setdefault("issues", [])
    total = result.get("total", 0)

    if banned_found:
        penalty = len(banned_found) * 3
        total -= penalty
        issues.append(f"Banned words penalty -{penalty}pts: {banned_found}")

    if entity_count < 15:
        penalty = (15 - entity_count) * 2
        total -= penalty
        issues.append(f"Entity count {entity_count}/15 penalty -{penalty}pts")

    if not has_faq:
        total -= 5
        issues.append("Missing FAQ section -5pts")

    if not has_tldr:
        total -= 3
        issues.append("Missing TL;DR -3pts")

    # CRITICAL: Hard FAIL for duplicates (inter-agent communication)
    if is_duplicate:
        total = min(total, 50)  # Cap at 50 — hard fail
        issues.append("CRITICAL: Article flagged as duplicate by AG·12 — max score 50")

    if has_cannibalization:
        total -= 10
        issues.append("Keyword cannibalization detected by AG·12 -10pts")

    total = max(0, total)
    result["total"] = total
    result["issues"] = issues

    # Final verdict
    if total >= 85:
        result["verdict"] = "PASS"
    elif total >= 70:
        result["verdict"] = "FLAG"
    else:
        result["verdict"] = "FAIL"

    update_state(article_id, "quality_result", result)
    update_state(article_id, "scores", result.get("scores", {}))
    update_state(article_id, "status", f"quality_{result['verdict'].lower()}")

    verdict = result["verdict"]
    verdict_icon = "✅" if verdict == "PASS" else ("⚠️" if verdict == "FLAG" else "❌")

    log_agent_completion(article_id, "AG·15", {
        "output_keys": ["quality_result", "scores"],
        "key_outputs": {
            "total": total,
            "verdict": verdict,
            "scores": result.get("scores", {}),
        },
        "metrics": {"quality_score": total},
        "warnings": issues[:5],
    })

    print(f"[AG·15] {verdict_icon} {verdict} | Score: {total}/110")
    scores = result.get("scores", {})
    for dim, score in scores.items():
        print(f"  {dim}: {score}")
    if issues:
        for issue in issues[:4]:
            print(f"  ⚠ {issue}")
    return result
