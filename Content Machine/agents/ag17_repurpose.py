"""AG·17 — Repurpose Agent: Converts article into Twitter thread, LinkedIn, Reddit, Pinterest."""

import anthropic
import json
import os
from config import ANTHROPIC_API_KEY
from tools.json_helper import extract_json
from shared_memory.memory import update_state, get_field, log_agent_completion

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    outline = get_field(article_id, "outline") or {}

    print(f"[AG·17] Repurposing: '{keyword}'")

    h1 = outline.get("h1", keyword)
    primary_angle = outline.get("primary_angle", "")
    sections = [s.get("h2", "") for s in outline.get("sections", [])[:5]]

    prompt = f"""
You are a social media content specialist. Repurpose this article for 4 platforms.

ARTICLE TITLE: {h1}
KEYWORD: {keyword}
PRIMARY ANGLE: {primary_angle}
KEY SECTIONS: {sections}

ARTICLE (first 3000 chars):
{draft[:3000]}

Return JSON with all 4 formats:
{{
    "twitter_thread": {{
        "tweets": [
            "Tweet 1: Hook — shocking stat or bold claim. Max 280 chars. No hashtags yet.",
            "Tweet 2: Context — why this matters",
            "Tweet 3: Key insight #1 (contrarian or surprising)",
            "Tweet 4: Key insight #2 (practical/actionable)",
            "Tweet 5: Common mistake people make",
            "Tweet 6: Pro tip most people don't know",
            "Tweet 7: CTA — 'Full breakdown here: [LINK] Thread summary in reply⬇️'"
        ]
    }},
    "linkedin_post": {{
        "hook": "First 1-2 lines (must make people click 'see more') — bold statement or question",
        "body": "3-5 short paragraphs. Use line breaks. Conversational but professional.",
        "cta": "End with a question to drive comments",
        "hashtags": ["#Tag1", "#Tag2", "#Tag3", "#Tag4", "#Tag5"]
    }},
    "reddit_comment": {{
        "subreddit_suggestions": ["r/relevantsubreddit1", "r/relevantsubreddit2"],
        "title": "post title (helpful framing, no clickbait)",
        "body": "Helpful, detailed comment/post. No promotion. Natural mention of article at end."
    }},
    "pinterest_description": {{
        "title": "Pin title — keyword-rich, max 100 chars",
        "description": "Description — keyword-rich, 300-500 chars, includes CTA"
    }}
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    repurposed = extract_json(raw, default={"raw": raw})

    # Save social content to file
    os.makedirs("output/social", exist_ok=True)
    slug = keyword.lower().replace(" ", "_")
    social_path = f"output/social/{slug}_social.json"
    with open(social_path, "w", encoding="utf-8") as f:
        json.dump(repurposed, f, ensure_ascii=False, indent=2)

    update_state(article_id, "repurposed_content", repurposed)
    update_state(article_id, "status", "repurposed")

    tweet_count = len(repurposed.get("twitter_thread", {}).get("tweets", []))

    log_agent_completion(article_id, "AG·17", {
        "output_keys": ["repurposed_content"],
        "key_outputs": {
            "twitter_tweets": tweet_count,
            "platforms": ["twitter", "linkedin", "reddit", "pinterest"],
            "saved_to": social_path,
        },
        "metrics": {"repurposed_platforms": 4},
    })

    print(f"[AG·17] Repurposed to 4 platforms. Twitter: {tweet_count} tweets. Saved: {social_path}")
    return repurposed
