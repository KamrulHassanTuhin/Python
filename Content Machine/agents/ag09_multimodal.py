"""AG·09 — Multimodal Coordinator: Plans all visual content + generates ImageObject schemas."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion
from tools.json_helper import extract_json

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    outline = get_field(article_id, "outline") or {}

    print(f"[AG·09] Multimodal planning: '{keyword}'")

    sections = outline.get("sections", [])

    prompt = f"""
You are a multimodal content strategist. Plan all visual elements for maximum engagement.

KEYWORD: "{keyword}"
CONTENT TYPE: {outline.get("content_type", "guide")}
SECTIONS: {json.dumps([s.get("h2") for s in sections])}

ARTICLE EXCERPT:
{draft[:3000]}

Plan visual content. Follow the 30px OCR rule for alt text: alt text must describe image content
clearly enough for a screen reader or AI vision system to understand the image.

Return JSON:
{{
    "hero_image": {{
        "description": "detailed description for designer/stock photo search",
        "alt_text": "descriptive alt text including keyword naturally",
        "placement": "after H1, before TL;DR"
    }},
    "infographics": [
        {{
            "title": "infographic title",
            "type": "process|comparison|stats|timeline|checklist",
            "content_points": ["point 1", "point 2", "point 3"],
            "placement_after_section": "H2 section title",
            "alt_text": "infographic alt text"
        }}
    ],
    "section_images": [
        {{
            "section": "H2 title",
            "description": "what image shows",
            "alt_text": "descriptive alt text",
            "type": "screenshot|photo|diagram|chart"
        }}
    ],
    "video_opportunities": [
        {{
            "topic": "video topic",
            "type": "tutorial|explainer|demo|comparison",
            "embed_after_section": "section name",
            "youtube_search_query": "what to search on YouTube"
        }}
    ]
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    media_plan = extract_json(raw, default={})

    # Append image notes to article draft
    alt_notes = "\n\n---\n## Image Notes (for publisher)\n\n"

    hero = media_plan.get("hero_image", {})
    if hero:
        alt_notes += f"**Hero Image:** {hero.get('description', '')}\n"
        alt_notes += f"- Alt text: `{hero.get('alt_text', '')}`\n"
        alt_notes += f"- Placement: {hero.get('placement', 'after H1')}\n\n"

    for img in media_plan.get("section_images", []):
        alt_notes += f"**Section: {img.get('section', '')}**\n"
        alt_notes += f"- Image: {img.get('description', '')}\n"
        alt_notes += f"- Alt text: `{img.get('alt_text', '')}`\n\n"

    for inf in media_plan.get("infographics", []):
        alt_notes += f"**Infographic: {inf.get('title', '')}**\n"
        alt_notes += f"- Type: {inf.get('type', '')} | After: {inf.get('placement_after_section', '')}\n"
        alt_notes += f"- Alt text: `{inf.get('alt_text', '')}`\n\n"

    current_draft = get_field(article_id, "draft")
    update_state(article_id, "draft", current_draft + alt_notes)
    update_state(article_id, "media_plan", media_plan)
    update_state(article_id, "status", "multimodal_done")

    img_count = len(media_plan.get("section_images", [])) + (1 if hero else 0)
    inf_count = len(media_plan.get("infographics", []))
    vid_count = len(media_plan.get("video_opportunities", []))

    log_agent_completion(article_id, "AG·09", {
        "output_keys": ["media_plan"],
        "key_outputs": {
            "images": img_count,
            "infographics": inf_count,
            "videos": vid_count,
        },
        "metrics": {"total_visual_assets": img_count + inf_count},
    })

    print(f"[AG·09] Media plan: {img_count} images, {inf_count} infographics, {vid_count} videos")
    return media_plan
