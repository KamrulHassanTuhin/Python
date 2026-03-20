"""AG·01 — Deep Researcher: Analyzes top 10 competitor pages + fetches real-time facts."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion
from tools.serper_tool import get_top_urls
from tools.firecrawl_tool import scrape_multiple
from tools.perplexity_tool import get_facts
from tools.json_helper import extract_json

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    subqueries = get_field(article_id, "subqueries") or []

    print(f"[AG·01] Deep researching: '{keyword}'")

    # Step 1: Get top 10 competitor URLs
    top_urls = get_top_urls(keyword, num=10)
    print(f"[AG·01] Scraping {len(top_urls)} competitor pages...")

    # Step 2: Scrape competitor content (top 10 as spec requires)
    scraped = scrape_multiple(top_urls, max_urls=10)
    competitor_texts = [
        {"url": s["url"], "content": s["content"][:4000]}
        for s in scraped if s["success"] and s["content"]
    ]
    print(f"[AG·01] Successfully scraped: {len(competitor_texts)}/10 pages")

    # Step 3: Fetch real-time facts + citations from Perplexity
    print("[AG·01] Fetching real-time facts from Perplexity...")
    facts_data = get_facts(f"Latest facts, statistics, data, and expert opinions about: {keyword}")
    facts = facts_data.get("answer", "")
    citations = facts_data.get("citations", [])

    # Step 4: Analyze with Claude — build full research brief
    competitor_summary = "\n\n---COMPETITOR---\n\n".join(
        [f"URL: {c['url']}\n{c['content']}" for c in competitor_texts[:5]]
    )

    prompt = f"""
You are a deep research analyst. Analyze competitor content and build a comprehensive research brief.

KEYWORD: "{keyword}"
SUB-QUERIES TO COVER: {json.dumps(subqueries[:10])}

TOP COMPETITOR CONTENT:
{competitor_summary[:5000]}

REAL-TIME FACTS FROM PERPLEXITY:
{facts[:2000]}

Build a research brief and return JSON:
{{
    "entities": ["list of 20+ named entities: tools, people, companies, concepts, technologies"],
    "key_facts": ["important facts — each with source attribution"],
    "statistics": ["specific stats with years: e.g., '47% of users... (2024)'"],
    "competitor_gaps": ["topics competitors covered poorly or missed entirely"],
    "unique_angles": ["3-5 content angles that would differentiate our article"],
    "questions_answered": {{"sub-query text": "one-sentence answer"}},
    "source_map": {{"fact": "source URL or name"}},
    "contradictions": ["places where sources disagree — note the disagreement"],
    "expert_opinions": ["notable expert quotes or positions on the topic"]
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    research = extract_json(raw, default={"raw": raw, "facts": facts})

    research["citations"] = citations
    research["top_urls"] = top_urls
    research["scraped_count"] = len(competitor_texts)

    update_state(article_id, "research", research)
    update_state(article_id, "status", "research_done")

    entity_count = len(research.get("entities", []))
    gap_count = len(research.get("competitor_gaps", []))

    log_agent_completion(article_id, "AG·01", {
        "output_keys": ["research"],
        "key_outputs": {
            "entity_count": entity_count,
            "gap_count": gap_count,
            "top_entities": research.get("entities", [])[:5],
            "top_gaps": research.get("competitor_gaps", [])[:3],
            "citations_count": len(citations),
        },
        "metrics": {
            "entities": entity_count,
            "pages_scraped": len(competitor_texts),
            "citations": len(citations),
        },
        "warnings": (
            ["Scraped fewer than 10 pages — some competitor data missing"]
            if len(competitor_texts) < 10 else []
        ),
    })

    print(f"[AG·01] Research complete. Entities: {entity_count}, Gaps: {gap_count}")
    return research
