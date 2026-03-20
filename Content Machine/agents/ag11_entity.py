"""AG·11 — Entity Authority Builder: Verifies entities via Wikidata, builds Organization schema."""

import anthropic
import json
import requests
from config import ANTHROPIC_API_KEY
from tools.json_helper import extract_json
from shared_memory.memory import update_state, get_field, log_agent_completion

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _check_wikidata(entity_name: str) -> dict:
    """Check if entity exists in Wikidata."""
    try:
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": entity_name,
            "language": "en",
            "format": "json",
            "limit": 1,
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        results = data.get("search", [])
        if results:
            return {
                "found": True,
                "wikidata_id": results[0].get("id"),
                "wikidata_url": f"https://www.wikidata.org/wiki/{results[0].get('id')}",
                "description": results[0].get("description", ""),
            }
        return {"found": False}
    except Exception:
        return {"found": False, "error": "Wikidata API unavailable"}


def _build_organization_schema(org_name: str, wikidata_result: dict) -> dict:
    """Build Organization JSON-LD schema with sameAs links."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": org_name,
        "url": "",
    }
    if wikidata_result.get("found"):
        schema["sameAs"] = [
            wikidata_result.get("wikidata_url", ""),
            f"https://en.wikipedia.org/wiki/{org_name.replace(' ', '_')}",
        ]
        schema["sameAs"] = [u for u in schema["sameAs"] if u]
    return schema


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    research = get_field(article_id, "research") or {}
    schema = get_field(article_id, "schema") or {}

    print(f"[AG·11] Entity authority building: '{keyword}'")

    # Extract entities from article using Claude
    prompt = f"""
Extract ALL named entities from this article.

Categories:
- persons: real people mentioned by name
- organizations: companies, brands, institutions
- products_tools: software, tools, products
- concepts: named methodologies, frameworks, terms
- technologies: specific tech stacks, platforms, APIs

Return JSON:
{{
    "persons": ["name1"],
    "organizations": ["org1"],
    "products_tools": ["tool1"],
    "concepts": ["concept1"],
    "technologies": ["tech1"]
}}

ARTICLE:
{draft[:5000]}
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    extracted = extract_json(raw, default={"persons": [], "organizations": [], "products_tools": [], "concepts": [], "technologies": []})

    # Wikidata check for top entities
    all_entities = (
        extracted.get("organizations", [])[:3]
        + extracted.get("persons", [])[:2]
        + extracted.get("products_tools", [])[:2]
    )

    wikidata_results = {}
    for entity in all_entities[:7]:
        wikidata_results[entity] = _check_wikidata(entity)

    # Build Organization schemas for major orgs
    org_schemas = []
    for org in extracted.get("organizations", [])[:3]:
        wd = wikidata_results.get(org, {})
        if wd.get("found"):
            org_schemas.append(_build_organization_schema(org, wd))

    # Save org schemas to schema state
    if org_schemas:
        current_schema = get_field(article_id, "schema") or {}
        current_schema["organizations"] = org_schemas
        current_schema_html = get_field(article_id, "schema_html") or ""
        for org_schema in org_schemas:
            current_schema_html += f'<script type="application/ld+json">\n{json.dumps(org_schema, indent=2)}\n</script>\n'
        update_state(article_id, "schema", current_schema)
        update_state(article_id, "schema_html", current_schema_html)

    total_count = sum(len(v) for v in extracted.values() if isinstance(v, list))

    result = {
        "extracted_entities": extracted,
        "total_count": total_count,
        "wikidata_checks": wikidata_results,
        "organization_schemas_built": len(org_schemas),
        "meets_minimum": total_count >= 15,
    }

    update_state(article_id, "entity_audit", result)
    update_state(article_id, "status", "entity_done")

    wikidata_verified = sum(1 for v in wikidata_results.values() if v.get("found"))
    status_icon = "✅" if result["meets_minimum"] else "❌"

    log_agent_completion(article_id, "AG·11", {
        "output_keys": ["entity_audit"],
        "key_outputs": {
            "total_entities": total_count,
            "meets_minimum": result["meets_minimum"],
            "wikidata_verified": wikidata_verified,
            "org_schemas": len(org_schemas),
        },
        "metrics": {"entity_count": total_count, "wikidata_verified": wikidata_verified},
        "warnings": (
            [f"Entity count {total_count} below minimum of 15"] if not result["meets_minimum"] else []
        ),
    })

    print(f"[AG·11] Entities: {total_count}/15 min {status_icon} | Wikidata: {wikidata_verified} verified | Org schemas: {len(org_schemas)}")
    return result
