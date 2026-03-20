"""AG·03 — Writer: Writes the full article draft following strict SOP rules."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion
from prompts.sop_prompts import WRITER_SOP

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

BANNED_WORDS = [
    "delve", "tapestry", "vibrant", "foster", "leverage", "utilize",
    "furthermore", "moreover", "in conclusion", "it's worth noting",
    "it is important to note", "in today's world", "game-changer",
    "revolutionary", "groundbreaking", "cutting-edge", "seamlessly",
    "crucial", "essential", "robust", "streamline", "synergy",
]

MIN_WORDS = 2500
TARGET_WORDS = 3500


def _validate_draft(draft: str) -> list[str]:
    """Check draft for SOP violations."""
    warnings = []
    word_count = len(draft.split())

    if word_count < MIN_WORDS:
        warnings.append(f"Word count too low: {word_count} (target: {TARGET_WORDS})")

    banned_found = [w for w in BANNED_WORDS if w in draft.lower()]
    if banned_found:
        warnings.append(f"Banned words found: {banned_found}")

    h2_count = draft.count("\n## ")
    if h2_count < 4:
        warnings.append(f"Too few H2 sections: {h2_count} (need 4+)")

    if "## faq" not in draft.lower() and "## frequently" not in draft.lower():
        warnings.append("Missing FAQ section")

    return warnings


def run(article_id: str) -> str:
    keyword = get_field(article_id, "keyword")
    niche = get_field(article_id, "niche")
    outline = get_field(article_id, "outline") or {}
    research = get_field(article_id, "research") or {}

    print(f"[AG·03] Writing article: '{keyword}'")

    h1 = outline.get("h1", keyword)
    sections = outline.get("sections", [])
    angle = outline.get("primary_angle", "")
    entities = research.get("entities", [])
    key_facts = research.get("key_facts", [])
    statistics = research.get("statistics", [])
    citations = research.get("citations", [])
    contradictions = research.get("contradictions", [])
    expert_opinions = research.get("expert_opinions", [])
    source_map = research.get("source_map", {})

    prompt = f"""
{WRITER_SOP}

Write a complete, publication-ready article. TARGET: {TARGET_WORDS} words minimum.

TITLE (H1): {h1}
KEYWORD: {keyword}
NICHE: {niche}
PRIMARY ANGLE: {angle}

OUTLINE TO FOLLOW EXACTLY:
{json.dumps(sections, indent=2)}

ENTITIES TO MENTION (use at least 15): {json.dumps(entities[:20])}
KEY FACTS (weave naturally): {json.dumps(key_facts[:10])}
STATISTICS (include with years): {json.dumps(statistics[:8])}
CITATIONS (reference as: "According to [source]..."): {json.dumps(citations[:5])}
EXPERT OPINIONS (quote or paraphrase): {json.dumps(expert_opinions[:3])}
CONTRADICTIONS (acknowledge where experts disagree): {json.dumps(contradictions[:2])}

MANDATORY WRITING RULES:
1. First paragraph (after H1): 2-sentence direct answer to the main keyword
2. Every H2 section opens with a 40-word BLUF (Bottom Line Up Front)
3. Each H2 section must be 300-500 words — write deeply, don't skim
4. Sentence burstiness: mix 3-word punchy sentences with 20-word detailed ones
5. Bold every key term on its FIRST mention only
6. ZERO banned words: {BANNED_WORDS}
7. Include at least 2 real-world examples per major section
8. Second-to-last section: ## Bottom Line (summary + recommendation)
9. FINAL section MUST be: ## Frequently Asked Questions
   — 5-7 questions using the exact wording a person would Google
   — Each answer: 2-4 sentences, direct and factual
10. Minimum {TARGET_WORDS} words total — if outline runs short, expand each section

Return clean markdown only. No preamble. No explanation.
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=10000,
        messages=[{"role": "user", "content": prompt}],
    )

    draft = response.content[0].text.strip()

    warnings = _validate_draft(draft)
    word_count = len(draft.split())

    update_state(article_id, "draft", draft)
    update_state(article_id, "status", "draft_done")

    log_agent_completion(article_id, "AG·03", {
        "output_keys": ["draft"],
        "key_outputs": {
            "word_count": word_count,
            "h2_count": draft.count("\n## "),
        },
        "metrics": {"word_count": word_count},
        "warnings": warnings,
    })

    print(f"[AG·03] Draft complete. Words: {word_count}")
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}")
    return draft
