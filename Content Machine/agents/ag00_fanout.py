"""AG·00 — Fan-out Mapper: Expands a keyword into 8-12 targeted sub-queries."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from tools.json_helper import extract_json
from shared_memory.memory import update_state, get_field, log_agent_completion
from tools.serper_tool import get_paa
from tools.dataforseo_tool import get_keyword_volume

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str) -> list[str]:
    keyword = get_field(article_id, "keyword")
    niche = get_field(article_id, "niche")

    print(f"[AG·00] Fan-out mapping: '{keyword}'")

    # Step 1: Get real PAA questions from Google
    paa_questions = get_paa(keyword)

    # Step 2: Generate sub-queries with Claude
    prompt = f"""
Keyword: "{keyword}"
Niche: {niche}
People Also Ask questions: {json.dumps(paa_questions)}

Generate 8-12 sub-queries covering ALL search intent angles:
- Definition / What is
- How to / Step-by-step process
- Comparison / vs alternatives
- Price / Cost / Value
- Common problems / Mistakes to avoid
- Best / Top / Recommended
- Beginner guide / Advanced tips
- Reviews / Is it worth it / Trust signals
- Zero-volume long-tail queries that standard tools miss

Rules:
- Each query must be a complete question someone would Google
- Cover both informational and commercial intent
- Include queries that rank for featured snippets
- Include "near me" or local variants if relevant to niche

Return ONLY a JSON array of strings:
["query 1", "query 2", ...]
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Parse JSON array
    subqueries = extract_json(raw, default=paa_questions[:10])

    # Step 3: Get search volume data for sub-queries (DataForSEO)
    volume_data = {}
    try:
        volume_results = get_keyword_volume(subqueries[:10])
        for item in volume_results:
            kw = item.get("keyword", "")
            vol = item.get("search_volume", 0) or 0
            volume_data[kw] = vol
        print(f"[AG·00] Volume data retrieved for {len(volume_data)} queries.")
    except Exception as e:
        print(f"[AG·00] DataForSEO volume check skipped: {e}")

    # Sort sub-queries: high volume first, zero-volume last (still valuable)
    if volume_data:
        subqueries.sort(key=lambda q: volume_data.get(q, 0), reverse=True)

    update_state(article_id, "subqueries", subqueries)
    update_state(article_id, "subquery_volumes", volume_data)
    update_state(article_id, "status", "fanout_done")

    log_agent_completion(article_id, "AG·00", {
        "output_keys": ["subqueries", "subquery_volumes"],
        "key_outputs": {
            "subquery_count": len(subqueries),
            "paa_count": len(paa_questions),
            "top_subqueries": subqueries[:3],
        },
        "metrics": {"total_subqueries": len(subqueries)},
    })

    print(f"[AG·00] Generated {len(subqueries)} sub-queries.")
    for i, q in enumerate(subqueries[:5], 1):
        vol = volume_data.get(q, "?")
        print(f"  {i}. {q} [vol: {vol}]")
    return subqueries
