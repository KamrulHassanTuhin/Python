"""AG·07 — Schema Builder: Generates full JSON-LD schema (Article + FAQ + ItemList + HowTo + ImageObject)."""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion
from tools.json_helper import extract_json
from datetime import datetime

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _extract_faq_pairs(draft: str) -> list[dict]:
    """Extract Q&A pairs from FAQ sections."""
    prompt = f"""
Extract all FAQ question-answer pairs from this article.
Focus on the FAQ section and any Q&A patterns throughout.
Return JSON array ONLY: [{{"question": "...", "answer": "..."}}]

ARTICLE:
{draft[:6000]}
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    return extract_json(raw, default=[])


def _extract_list_items(draft: str, h1: str) -> list[str]:
    """Extract numbered/bulleted list items for ItemList schema."""
    import re
    items = re.findall(r'^\d+\.\s+(.+)$', draft, re.MULTILINE)
    if not items:
        items = re.findall(r'^[-*]\s+\*\*(.+?)\*\*', draft, re.MULTILINE)
    return items[:10]


def _extract_howto_steps(draft: str) -> list[dict]:
    """Extract step-by-step instructions for HowTo schema."""
    import re
    steps = re.findall(r'(?:step\s+\d+|^\d+\.)\s*[:\-]?\s*(.+?)(?=\n)', draft, re.IGNORECASE | re.MULTILINE)
    return [{"name": s.strip(), "text": s.strip()} for s in steps[:8] if len(s.strip()) > 10]


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    outline = get_field(article_id, "outline") or {}
    draft = get_field(article_id, "draft")
    media_plan = get_field(article_id, "media_plan") or {}
    entity_audit = get_field(article_id, "entity_audit") or {}

    print(f"[AG·07] Building schema for: '{keyword}'")

    h1 = outline.get("h1", keyword)
    meta_desc = outline.get("meta_description", "")
    content_type = outline.get("content_type", "guide")
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    today = datetime.now().strftime("%Y-%m-%d")

    faq_pairs = _extract_faq_pairs(draft)
    list_items = _extract_list_items(draft, h1)
    howto_steps = _extract_howto_steps(draft)
    images = media_plan.get("section_images", [])
    hero_image = media_plan.get("hero_image", {})

    schemas = {}
    schema_html = ""

    # ── 1. Article Schema ─────────────────────────────────────────
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": h1,
        "description": meta_desc,
        "keywords": keyword,
        "datePublished": now,
        "dateModified": now,
        "author": {
            "@type": "Person",
            "name": "Site Author",
            "url": "https://yoursite.com/about/",
        },
        "publisher": {
            "@type": "Organization",
            "name": "Your Site Name",
            "url": "https://yoursite.com",
            "logo": {
                "@type": "ImageObject",
                "url": "https://yoursite.com/logo.png",
                "width": 600,
                "height": 60,
            },
            "sameAs": [
                "https://twitter.com/yoursite",
                "https://linkedin.com/company/yoursite",
            ],
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": f"https://yoursite.com/{keyword.lower().replace(' ', '-')}/",
        },
        "inLanguage": "en-US",
    }
    schemas["article"] = article_schema

    # ── 2. FAQPage Schema ─────────────────────────────────────────
    if faq_pairs:
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": pair["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": pair["answer"],
                    },
                }
                for pair in faq_pairs[:10]
            ],
        }
        schemas["faq"] = faq_schema

    # ── 3. ItemList Schema (for listicles) ────────────────────────
    if list_items and content_type in ("listicle", "comparison", "guide"):
        itemlist_schema = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": h1,
            "description": meta_desc,
            "numberOfItems": len(list_items),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "name": item,
                }
                for i, item in enumerate(list_items)
            ],
        }
        schemas["itemlist"] = itemlist_schema

    # ── 4. HowTo Schema (for tutorials/guides) ───────────────────
    if howto_steps and content_type in ("tutorial", "guide"):
        howto_schema = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": h1,
            "description": meta_desc,
            "totalTime": "PT15M",
            "step": [
                {
                    "@type": "HowToStep",
                    "position": i + 1,
                    "name": step["name"],
                    "text": step["text"],
                }
                for i, step in enumerate(howto_steps)
            ],
        }
        schemas["howto"] = howto_schema

    # ── 5. ImageObject Schemas ────────────────────────────────────
    image_schemas = []
    if hero_image:
        image_schemas.append({
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "name": hero_image.get("alt_text", h1),
            "description": hero_image.get("description", ""),
            "contentUrl": f"https://yoursite.com/images/{keyword.lower().replace(' ', '-')}-hero.jpg",
            "caption": hero_image.get("alt_text", ""),
        })
    for img in images[:3]:
        image_schemas.append({
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "name": img.get("alt_text", ""),
            "description": img.get("description", ""),
            "caption": img.get("alt_text", ""),
        })
    if image_schemas:
        schemas["images"] = image_schemas

    # ── Build HTML script tags ────────────────────────────────────
    for name, schema in schemas.items():
        if isinstance(schema, list):
            for s in schema:
                schema_html += f'<script type="application/ld+json">\n{json.dumps(s, indent=2)}\n</script>\n'
        else:
            schema_html += f'<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>\n'

    update_state(article_id, "schema", schemas)
    update_state(article_id, "schema_html", schema_html)
    update_state(article_id, "status", "schema_done")

    schema_types = list(schemas.keys())

    log_agent_completion(article_id, "AG·07", {
        "output_keys": ["schema", "schema_html"],
        "key_outputs": {
            "schema_types": schema_types,
            "faq_pairs": len(faq_pairs),
            "list_items": len(list_items),
            "howto_steps": len(howto_steps),
            "image_schemas": len(image_schemas),
        },
        "metrics": {"schema_count": len(schemas)},
        "warnings": (
            ["ItemList schema skipped — no list items found"] if not list_items else []
        ) + (
            ["HowTo schema skipped — no steps found"] if not howto_steps else []
        ),
    })

    print(f"[AG·07] Schemas built: {schema_types}")
    print(f"[AG·07] FAQ pairs: {len(faq_pairs)} | List items: {len(list_items)} | HowTo steps: {len(howto_steps)}")
    return schemas
