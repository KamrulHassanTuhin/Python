"""AG·02 — Strategist: Designs H1/H2/H3 article outline. Each H2 answers one sub-query."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion, get_pipeline_summary
from tools.json_helper import extract_json

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    niche = get_field(article_id, "niche")
    subqueries = get_field(article_id, "subqueries") or []
    research = get_field(article_id, "research") or {}
    pipeline = get_pipeline_summary(article_id)

    print(f"[AG·02] Building strategy for: '{keyword}'")

    gaps = research.get("competitor_gaps", [])
    angles = research.get("unique_angles", [])
    entities = research.get("entities", [])
    questions_answered = research.get("questions_answered", {})

    prompt = f"""
You are an SEO strategist. Design the optimal article structure.

KEYWORD: "{keyword}"
NICHE: {niche}
SUB-QUERIES (map each to an H2): {json.dumps(subqueries)}
COMPETITOR GAPS: {json.dumps(gaps)}
UNIQUE ANGLES: {json.dumps(angles)}
KEY ENTITIES TO USE: {json.dumps(entities[:15])}
KNOWN ANSWERS: {json.dumps(questions_answered)}

Structure rules:
- Each H2 MUST directly answer one sub-query
- First H2 = direct answer section for GEO (answer keyword in first 200 words)
- Include exactly ONE listicle section (Top X / Best Y / X Ways to...)
- Second-to-last H2 = Bottom Line / Summary
- Last H2 = FAQ (exact sub-query wording as questions)
- H3s break each H2 into scannable subsections

Return JSON:
{{
    "content_type": "guide|comparison|listicle|tutorial|review",
    "primary_angle": "the unique differentiating angle",
    "h1": "exact H1 title (include primary keyword)",
    "meta_description": "155-160 character meta description with keyword",
    "sections": [
        {{
            "h2": "Section Title",
            "answers_query": "exact sub-query this section answers",
            "h3s": ["Subsection 1", "Subsection 2"],
            "content_notes": "key points to cover, entities to mention",
            "word_target": 300,
            "section_type": "intro|standard|listicle|comparison|faq|conclusion"
        }}
    ],
    "internal_link_anchors": ["natural anchor text 1", "anchor text 2"],
    "featured_snippet_target": "sub-query most likely to win a featured snippet",
    "estimated_word_count": 2500
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    outline = extract_json(raw, default={"raw": raw, "h1": keyword})

    update_state(article_id, "outline", outline)
    update_state(article_id, "status", "strategy_done")

    section_count = len(outline.get("sections", []))

    log_agent_completion(article_id, "AG·02", {
        "output_keys": ["outline"],
        "key_outputs": {
            "h1": outline.get("h1"),
            "content_type": outline.get("content_type"),
            "section_count": section_count,
            "primary_angle": outline.get("primary_angle"),
            "word_target": outline.get("estimated_word_count"),
        },
        "metrics": {"sections": section_count},
    })

    print(f"[AG·02] Outline: {outline.get('h1')}")
    print(f"[AG·02] Type: {outline.get('content_type')} | Sections: {section_count}")
    return outline
