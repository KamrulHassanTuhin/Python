"""AG·06 — GEO Optimizer: Optimizes for AI search engines (Copilot, Gemini, Perplexity)."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion, get_pipeline_summary
from prompts.sop_prompts import GEO_SOP
from datetime import datetime

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str) -> str:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    subqueries = get_field(article_id, "subqueries") or []
    pipeline = get_pipeline_summary(article_id)

    print(f"[AG·06] GEO optimizing: '{keyword}'")

    current_date = datetime.now().strftime("%B %Y")
    current_year = datetime.now().year

    # Read what previous agents produced
    word_count_before = len(draft.split())

    prompt = f"""
{GEO_SOP}

KEYWORD: "{keyword}"
CURRENT DATE: {current_date}
PIPELINE CONTEXT: {json.dumps(pipeline)}
SUB-QUERIES (use EXACT wording in FAQ): {json.dumps(subqueries)}

ARTICLE:
{draft}

Apply ALL these GEO optimizations:

UNIVERSAL (all AI platforms):
1. First 200 words MUST contain a direct, clear answer to: "{keyword}"
   — If not, rewrite the opening to include it
2. Add "Last updated: {current_date}" after the first paragraph
3. FAQ section must use the EXACT sub-query wording as questions
4. Add citation patterns: "According to [Source], ..." at least 3 times
5. Include at least 2 statistics with years: "As of {current_year}, ..."

COPILOT OPTIMIZATION (breadth):
6. Every major angle covered at least briefly
7. Comparison table or structured list present

GEMINI OPTIMIZATION (depth):
8. At least 2 sections with 400+ word deep dives
9. Step-by-step numbered processes where applicable

PERPLEXITY OPTIMIZATION (freshness):
10. Freshness phrases: "As of {current_date}", "Recently updated:", "Current state:"
11. Version or iteration number if applicable

Return the COMPLETE optimized article in markdown. No preamble.
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    optimized = response.content[0].text.strip()
    word_count_after = len(optimized.split())

    update_state(article_id, "draft", optimized)
    update_state(article_id, "status", "geo_done")

    # Check first 200 words for direct answer
    first_200 = " ".join(optimized.split()[:200]).lower()
    has_direct_answer = keyword.lower() in first_200
    has_freshness = "last updated" in optimized.lower() or "as of" in optimized.lower()
    has_faq = "## faq" in optimized.lower() or "## frequently" in optimized.lower()

    warnings = []
    if not has_direct_answer:
        warnings.append("Direct answer may not be in first 200 words")
    if not has_freshness:
        warnings.append("Missing freshness signals (Last updated / As of)")
    if not has_faq:
        warnings.append("FAQ section not detected")

    log_agent_completion(article_id, "AG·06", {
        "output_keys": ["draft"],
        "key_outputs": {
            "word_count": word_count_after,
            "has_direct_answer": has_direct_answer,
            "has_freshness_signals": has_freshness,
            "has_faq": has_faq,
        },
        "metrics": {
            "word_count_before": word_count_before,
            "word_count_after": word_count_after,
        },
        "warnings": warnings,
    })

    print(f"[AG·06] GEO done. Words: {word_count_after} | Direct answer: {has_direct_answer} | FAQ: {has_faq}")
    return optimized
