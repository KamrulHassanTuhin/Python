"""AG·08 — Engagement Designer: Adds TL;DR, ToC, Key Takeaways, callouts, Bottom Line."""

import anthropic
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion, get_pipeline_summary

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str) -> str:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    outline = get_field(article_id, "outline") or {}
    subqueries = get_field(article_id, "subqueries") or []

    print(f"[AG·08] Adding engagement elements: '{keyword}'")

    sections = outline.get("sections", [])
    toc_items = [s.get("h2", "") for s in sections if s.get("h2")]

    # Build Table of Contents
    toc = "## Table of Contents\n\n"
    for i, item in enumerate(toc_items, 1):
        anchor = item.lower().replace(" ", "-").replace("?", "").replace(":", "").replace("'", "")
        toc += f"{i}. [{item}](#{anchor})\n"

    has_faq = "## faq" in draft.lower() or "## frequently" in draft.lower()

    faq_instruction = ""
    if not has_faq:
        faq_qs = subqueries[:5] if subqueries else [
            f"What is the best {keyword}?",
            f"How does {keyword} work?",
            f"Is {keyword} worth it?",
            f"What are the alternatives to {keyword}?",
            f"How much does {keyword} cost?",
        ]
        faq_instruction = f"""
7. **FAQ Section** — append at the very END of the article (CRITICAL — missing from draft):
   ## Frequently Asked Questions

   Use EXACTLY these questions (word-for-word):
   {chr(10).join(f'   **{q}**' + chr(10) + '   [2-3 sentence direct answer]' for q in faq_qs)}
"""

    prompt = f"""
You are an engagement designer. Enhance this article to maximize dwell time and reader engagement.

TABLE OF CONTENTS (pre-built):
{toc}

ARTICLE:
{draft}

Add these engagement elements (do not modify existing content, only ADD):

1. **TL;DR Box** — insert RIGHT after the H1 title line:
   > **TL;DR:** [2-3 sentences: what is it, the main recommendation, and one key insight]

2. **Table of Contents** — insert after TL;DR:
   {toc}

3. **Key Takeaways box** — insert after the first H2 section ends:
   > **Key Takeaways**
   > - [Takeaway 1 — specific and actionable]
   > - [Takeaway 2]
   > - [Takeaway 3]
   > - [Takeaway 4]
   > - [Takeaway 5]

4. **Pro Tip callout** — add after the most technical section:
   > **⚡ Pro Tip:** [specific, actionable tip readers can use immediately]

5. **Warning callout** — add where a common mistake is discussed:
   > **⚠️ Common Mistake:** [what people get wrong and how to avoid it]

6. **Stat highlight callout** — add near the strongest statistic:
   > **📊 Key Stat:** [statistic with source and year]
{faq_instruction}
Rules:
- Each addition must be in a DIFFERENT section of the article
- No duplicate element types in the same section
- Callouts should feel organic, not forced
- Keep all existing content intact

Return the COMPLETE enhanced article in markdown. No preamble.
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    enhanced = response.content[0].text.strip()
    word_count = len(enhanced.split())

    has_tldr = "tl;dr" in enhanced.lower() or "tldr" in enhanced.lower()
    has_toc = "table of contents" in enhanced.lower()
    has_takeaways = "key takeaways" in enhanced.lower()
    has_faq_after = "## faq" in enhanced.lower() or "## frequently" in enhanced.lower()

    update_state(article_id, "draft", enhanced)
    update_state(article_id, "status", "engagement_done")

    warnings = []
    if not has_tldr:
        warnings.append("TL;DR not found in output")
    if not has_takeaways:
        warnings.append("Key Takeaways not found")
    if not has_faq_after:
        warnings.append("FAQ section still missing after engagement pass")

    log_agent_completion(article_id, "AG·08", {
        "output_keys": ["draft"],
        "key_outputs": {
            "word_count": word_count,
            "has_tldr": has_tldr,
            "has_toc": has_toc,
            "has_takeaways": has_takeaways,
            "has_faq": has_faq_after,
        },
        "metrics": {"word_count": word_count},
        "warnings": warnings,
    })

    print(f"[AG·08] Engagement elements added. Words: {word_count}")
    print(f"[AG·08] TL;DR: {has_tldr} | ToC: {has_toc} | Takeaways: {has_takeaways} | FAQ: {has_faq_after}")
    return enhanced
