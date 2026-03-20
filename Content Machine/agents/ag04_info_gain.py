"""AG·04 — Info Gain Injector: Adds unique value competitors missed. Boosts originalContentScore."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion
from tools.sapling_tool import check_ai_content

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _check_originality(text: str) -> dict:
    """Check AI content score via Sapling AI (free replacement for Originality.ai)."""
    return check_ai_content(text)


def run(article_id: str) -> str:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    research = get_field(article_id, "research") or {}

    print(f"[AG·04] Info gain injection for: '{keyword}'")

    gaps = research.get("competitor_gaps", [])
    angles = research.get("unique_angles", [])
    key_facts = research.get("key_facts", [])
    contradictions = research.get("contradictions", [])
    expert_opinions = research.get("expert_opinions", [])

    # Check original score before enhancement
    orig_before = _check_originality(draft)
    if not orig_before.get("skipped"):
        print(f"[AG·04] Originality before: {orig_before.get('score', '?')}%")

    prompt = f"""
You are an Info Gain specialist. Make this article MORE valuable than all top competitors.

KEYWORD: "{keyword}"
COMPETITOR GAPS (things they missed): {json.dumps(gaps)}
UNIQUE ANGLES TO EXPLOIT: {json.dumps(angles)}
ADDITIONAL FACTS: {json.dumps(key_facts[:5])}
CONTRADICTIONS IN SOURCES: {json.dumps(contradictions)}
EXPERT OPINIONS: {json.dumps(expert_opinions[:3])}

CURRENT DRAFT:
{draft}

Enhance by adding these elements (add 200-400 words total, do NOT rewrite):
1. A "What Most Guides Miss" callout — one key insight competitors skipped
2. One contrarian or counterintuitive perspective (with reasoning)
3. One data point or statistic not in the current draft
4. Acknowledge one point where experts disagree (if contradictions exist)
5. Strengthen the weakest section with 1-2 additional paragraphs

Rules:
- ADD content, do not rewrite existing content
- Each addition must genuinely increase information value
- No filler. No padding. Every sentence earns its place.
- Keep banned words policy: no "delve", "leverage", "utilize", etc.

Return the COMPLETE enhanced article in markdown.
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    enhanced = response.content[0].text.strip()

    # Check original score after enhancement
    orig_after = _check_originality(enhanced)
    if not orig_after.get("skipped"):
        print(f"[AG·04] Originality after: {orig_after.get('score', '?')}%")

    update_state(article_id, "draft", enhanced)
    update_state(article_id, "originality_scores", {
        "before": orig_before,
        "after": orig_after,
    })
    update_state(article_id, "status", "info_gain_done")

    words_added = len(enhanced.split()) - len(draft.split())

    log_agent_completion(article_id, "AG·04", {
        "output_keys": ["draft", "originality_scores"],
        "key_outputs": {
            "words_added": words_added,
            "originality_before": orig_before.get("score"),
            "originality_after": orig_after.get("score"),
        },
        "metrics": {"words_added": words_added},
    })

    print(f"[AG·04] Info gain complete. Words added: +{words_added}")
    return enhanced
