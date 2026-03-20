"""AG·13 — Internal Link Builder: Suggests semantic internal links and resolves placeholders."""

import anthropic
import json
import re
from config import ANTHROPIC_API_KEY
from tools.json_helper import extract_json
from shared_memory.memory import update_state, get_field, log_agent_completion, _load

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _get_published_articles(current_id: str) -> list[dict]:
    """Get all articles that have a URL or output path."""
    data = _load()
    published = []
    for aid, state in data.items():
        if aid == current_id or aid.startswith("_"):
            continue
        if state.get("draft"):
            published.append({
                "id": aid,
                "keyword": state.get("keyword", ""),
                "h1": state.get("outline", {}).get("h1", state.get("keyword", "")),
                "url": state.get("output_path", "") or f"/articles/{state.get('keyword', '').lower().replace(' ', '-')}/",
                "excerpt": state.get("draft", "")[:250],
            })
    return published[:20]


def _resolve_link_placeholders(draft: str, link_map: dict) -> str:
    """
    Resolve INTERNAL_LINK:target_keyword placeholders to actual URLs.
    link_map = {keyword: url}
    """
    def replace_link(match):
        target_keyword = match.group(1).replace("INTERNAL_LINK:", "")
        url = link_map.get(target_keyword, f"/articles/{target_keyword.lower().replace(' ', '-')}/")
        return f"({url})"

    resolved = re.sub(r'\(INTERNAL_LINK:([^)]+)\)', replace_link, draft)
    return resolved


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    outline = get_field(article_id, "outline") or {}

    print(f"[AG·13] Internal link building: '{keyword}'")

    published = _get_published_articles(article_id)

    if not published:
        print("[AG·13] No other articles yet — skipping link suggestions.")
        result = {"links_added": 0, "suggestions": [], "note": "No other articles in database yet"}
        update_state(article_id, "internal_links", result)
        log_agent_completion(article_id, "AG·13", {
            "output_keys": ["internal_links"],
            "key_outputs": {"links_added": 0},
            "metrics": {"internal_links": 0},
        })
        return result

    prompt = f"""
You are an internal linking specialist. Find the best semantic linking opportunities.

CURRENT ARTICLE: "{keyword}"
CURRENT OUTLINE: {json.dumps([s.get("h2") for s in outline.get("sections", [])[:6]])}

AVAILABLE ARTICLES TO LINK TO:
{json.dumps(published, indent=2)}

Rules for quality internal links:
1. Link must be semantically relevant to the sentence context
2. Anchor text must be descriptive — not "click here" or "read more"
3. 3-5 links maximum (do not over-link)
4. Hub pages (broad topics) get priority over narrow articles
5. Each link should appear in a different section

Return JSON:
{{
    "suggestions": [
        {{
            "anchor_text": "exact phrase to hyperlink in the article",
            "target_keyword": "keyword of article to link to",
            "target_url": "URL from available articles list",
            "section": "which H2 this link appears in",
            "semantic_reason": "why this link is contextually relevant"
        }}
    ]
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    link_plan = extract_json(raw, default={"suggestions": []})

    suggestions = link_plan.get("suggestions", [])

    # Build keyword → URL map
    link_map = {p["keyword"]: p["url"] for p in published}

    # Inject INTERNAL_LINK placeholders into draft
    updated_draft = draft
    links_added = 0

    for sug in suggestions[:5]:
        anchor = sug.get("anchor_text", "")
        target_kw = sug.get("target_keyword", "")
        if anchor and target_kw and anchor in updated_draft:
            updated_draft = updated_draft.replace(
                anchor,
                f"[{anchor}](INTERNAL_LINK:{target_kw})",
                1,
            )
            links_added += 1

    # Immediately resolve placeholders (fixes the critical bug)
    updated_draft = _resolve_link_placeholders(updated_draft, link_map)

    result = {
        "suggestions": suggestions,
        "links_added": links_added,
        "link_map": link_map,
    }

    update_state(article_id, "draft", updated_draft)
    update_state(article_id, "internal_links", result)
    update_state(article_id, "status", "links_done")

    log_agent_completion(article_id, "AG·13", {
        "output_keys": ["draft", "internal_links"],
        "key_outputs": {
            "links_added": links_added,
            "links_suggested": len(suggestions),
        },
        "metrics": {"internal_links": links_added},
    })

    print(f"[AG·13] Internal links added and resolved: {links_added}")
    return result
