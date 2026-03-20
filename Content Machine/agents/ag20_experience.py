"""AG·20 — Experience Formatter: Converts raw user experience bullets into natural first-person prose."""

import anthropic
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion
from prompts.sop_prompts import EXPERIENCE_FORMATTER_SOP

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str, experience_bullets: list[str] | None = None) -> str:
    """
    Converts 5 raw experience bullets into natural first-person prose
    and injects them at 3 strategic locations in the article.

    experience_bullets format:
    [
        "What you did: used X tool for 3 months",
        "Result: traffic increased by 47%",
        "Mistake: forgot to configure Y setting",
        "Unexpected discovery: Z feature works better than expected",
        "Genuine opinion: this tool is overrated for small sites",
    ]

    IMPORTANT: Never fabricate. If no bullets provided, skip.
    Bullets are saved to shared memory so they survive retry loops.
    """
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")

    # If bullets passed in, save them (persists across retries)
    if experience_bullets:
        update_state(article_id, "experience_bullets", experience_bullets)
    else:
        # Try to load from memory (surviving a retry)
        experience_bullets = get_field(article_id, "experience_bullets") or []

    if not experience_bullets:
        print("[AG·20] No experience bullets — skipping.")
        return draft

    print(f"[AG·20] Formatting {len(experience_bullets)} experience bullets: '{keyword}'")

    bullets_text = "\n".join([f"• {b}" for b in experience_bullets])

    prompt = f"""
{EXPERIENCE_FORMATTER_SOP}

KEYWORD: "{keyword}"

RAW EXPERIENCE BULLETS (do NOT fabricate beyond these):
{bullets_text}

ARTICLE TO ENHANCE:
{draft}

Instructions:
1. Convert the raw bullets into natural, compelling first-person prose
2. Formats to use: "I tested...", "I found that...", "I made this mistake...", "What surprised me was..."
3. Inject at exactly 3 strategic locations:
   - After first H2 section (establishes credibility early)
   - In the middle of article (reinforces with specific result/data)
   - Before the Bottom Line or FAQ section (personal final take)
4. Each injection: 2-4 sentences, flows naturally with surrounding text
5. CRITICAL: Only use what was provided. Never invent numbers, tools, or outcomes.
6. Maintain the article's existing burstiness (short + long sentences)
7. Do NOT add [EXPERIENCE NOTE] markers — integrate seamlessly

Return the COMPLETE article in markdown with experience blocks woven in.
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    enhanced = response.content[0].text.strip()

    update_state(article_id, "draft", enhanced)
    update_state(article_id, "experience_added", True)
    update_state(article_id, "status", "experience_done")

    words_added = len(enhanced.split()) - len(draft.split())

    log_agent_completion(article_id, "AG·20", {
        "output_keys": ["draft"],
        "key_outputs": {
            "bullets_used": len(experience_bullets),
            "words_added": words_added,
            "injections": 3,
        },
        "metrics": {"experience_words_added": words_added},
    })

    print(f"[AG·20] Experience injected at 3 locations. Words added: +{words_added}")
    return enhanced
