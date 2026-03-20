"""AG·14 — Freshness Scheduler: Sets update schedule, flags dated claims, adds freshness signals."""

import json
import re
from datetime import datetime, timedelta
from shared_memory.memory import update_state, get_field, log_agent_completion


def _find_dated_claims(draft: str) -> list[str]:
    """Find all dated claims, statistics, and time-sensitive data in the article."""
    patterns = [
        r'\b20\d{2}\b',                             # Years like 2023, 2024
        r'\b\d+%\b',                                 # Percentages
        r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|M|B))?\b',  # Dollar amounts
        r'\b\d+\s*(?:million|billion|thousand)\b',   # Large numbers
        r'\b(?:as of|since|updated|published)\s+\w+', # Temporal markers
        r'\b(?:latest|current|recent|new)\s+\w+',    # Freshness words
    ]
    claims = []
    for pattern in patterns:
        matches = re.findall(pattern, draft, re.IGNORECASE)
        claims.extend(matches[:3])
    return list(dict.fromkeys(claims))[:12]  # Deduplicated, max 12


def run(article_id: str) -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")
    niche = get_field(article_id, "niche") or "general"

    print(f"[AG·14] Freshness scheduling: '{keyword}'")

    now = datetime.now()
    dated_claims = _find_dated_claims(draft)

    # Niche-based update frequency
    high_velocity_niches = ["ai", "technology", "crypto", "finance", "news", "software", "saas"]
    medium_velocity_niches = ["health", "fitness", "nutrition", "travel", "marketing", "seo"]

    if any(n in niche.lower() for n in high_velocity_niches):
        frequency = "monthly"
        first_review_days = 14
    elif any(n in niche.lower() for n in medium_velocity_niches):
        frequency = "quarterly"
        first_review_days = 30
    else:
        frequency = "bi-annual"
        first_review_days = 60

    schedule = {
        "first_review": (now + timedelta(days=first_review_days)).strftime("%Y-%m-%d"),
        "next_review": (now + timedelta(days=first_review_days)).strftime("%Y-%m-%d"),
        "quarterly": (now + timedelta(days=90)).strftime("%Y-%m-%d"),
        "annual_refresh": (now + timedelta(days=365)).strftime("%Y-%m-%d"),
        "recommended_frequency": frequency,
    }

    # Update checklist
    update_checklist = [
        "Verify all statistics are still accurate",
        "Check if tools/products/prices mentioned have changed",
        "Look for new PAA questions on this topic",
        "Check competitor rankings for new top-10 content",
        "Update 'Last updated' date in article",
        "Add any new developments in the niche",
    ]
    if dated_claims:
        update_checklist.append(f"Re-verify {len(dated_claims)} dated claims/statistics found")

    # Add freshness footer if not present
    freshness_note = (
        f"\n\n---\n"
        f"*Last updated: {now.strftime('%B %Y')} | "
        f"Next review scheduled: {schedule['next_review']}*\n"
    )

    current_draft = get_field(article_id, "draft")
    has_freshness_footer = "last updated:" in current_draft.lower()

    if not has_freshness_footer:
        # Insert before FAQ section if it exists, otherwise append
        if "## faq" in current_draft.lower() or "## frequently" in current_draft.lower():
            sections = re.split(r'(?=\n## )', current_draft)
            faq_idx = next((i for i, s in enumerate(sections) if "faq" in s.lower() or "frequently" in s.lower()), -1)
            if faq_idx > 0:
                sections.insert(faq_idx, freshness_note)
                updated_draft = "".join(sections)
            else:
                updated_draft = current_draft + freshness_note
        else:
            updated_draft = current_draft + freshness_note
        update_state(article_id, "draft", updated_draft)

    result = {
        "created_date": now.strftime("%Y-%m-%d"),
        "niche_frequency": frequency,
        "schedule": schedule,
        "dated_claims_count": len(dated_claims),
        "dated_claims_sample": dated_claims[:5],
        "update_checklist": update_checklist,
    }

    update_state(article_id, "freshness_schedule", result)
    update_state(article_id, "status", "freshness_done")

    log_agent_completion(article_id, "AG·14", {
        "output_keys": ["freshness_schedule"],
        "key_outputs": {
            "frequency": frequency,
            "next_review": schedule["next_review"],
            "dated_claims": len(dated_claims),
        },
        "metrics": {"dated_claims_count": len(dated_claims)},
    })

    print(f"[AG·14] Schedule set: {frequency} | Next review: {schedule['next_review']} | Dated claims: {len(dated_claims)}")
    return result
