"""AG·10 — Technical Auditor: Checks robots.txt, llms.txt, H-tags, alt text, technical SEO."""

import json
import re
import requests
from shared_memory.memory import update_state, get_field, log_agent_completion


def _check_site_technical(site_url: str) -> dict:
    """Audit robots.txt, llms.txt for a live site."""
    if not site_url:
        return {"status": "skipped", "note": "No site URL — configure SITE_URL in .env"}

    result = {
        "robots_found": False,
        "citation_bots_allowed": False,
        "training_bots_blocked": False,
        "llms_txt_found": False,
        "recommendations": [],
        "issues": [],
    }

    # Check robots.txt
    try:
        r = requests.get(f"{site_url.rstrip('/')}/robots.txt", timeout=10)
        if r.status_code == 200:
            result["robots_found"] = True
            content = r.text.lower()

            # Check citation bots (should be ALLOWED)
            citation_bots = ["gptbot", "anthropic-ai", "claudebot", "perplexitybot", "cohere-ai"]
            allowed = [b for b in citation_bots if b in content and "disallow" not in content.split(b)[1][:50]]
            result["citation_bots_allowed"] = len(allowed) > 0

            # Check training bots (should be BLOCKED)
            training_bots = ["ccbot", "common crawl", "diffbot"]
            blocked = [b for b in training_bots if b in content]
            result["training_bots_blocked"] = len(blocked) > 0

            if not result["citation_bots_allowed"]:
                result["recommendations"].append(
                    "Add to robots.txt:\n"
                    "User-agent: GPTBot\nAllow: /\n"
                    "User-agent: anthropic-ai\nAllow: /\n"
                    "User-agent: PerplexityBot\nAllow: /"
                )
    except Exception as e:
        result["issues"].append(f"robots.txt fetch failed: {e}")

    # Check llms.txt
    try:
        llms_r = requests.get(f"{site_url.rstrip('/')}/llms.txt", timeout=5)
        result["llms_txt_found"] = llms_r.status_code == 200
        if not result["llms_txt_found"]:
            result["recommendations"].append(
                "Create /llms.txt — Perplexity and Claude read this for site context.\n"
                "Template: https://llmstxt.org/"
            )
    except Exception:
        result["llms_txt_found"] = False

    return result


def _audit_article_content(draft: str, keyword: str) -> dict:
    """Deep-audit the article content for technical SEO issues."""
    issues = []
    recommendations = []
    word_count = len(draft.split())

    # Word count
    if word_count < 1200:
        issues.append(f"Word count critically low: {word_count} words (minimum 1200)")
    elif word_count < 1800:
        recommendations.append(f"Word count low: {word_count} words (recommended 1800+)")

    # H-tag structure
    h1_lines = [l for l in draft.split("\n") if l.startswith("# ") and not l.startswith("## ")]
    h2_count = len(re.findall(r'^## .+', draft, re.MULTILINE))
    h3_count = len(re.findall(r'^### .+', draft, re.MULTILINE))

    if len(h1_lines) == 0:
        issues.append("No H1 found — add # Title at the top")
    if len(h1_lines) > 1:
        issues.append(f"Multiple H1 found ({len(h1_lines)}) — must have exactly one H1")
    if h2_count < 3:
        issues.append(f"Too few H2 sections: {h2_count} (minimum 3)")

    # Keyword in H1
    if h1_lines:
        h1_text = h1_lines[0].lower()
        if keyword.lower() not in h1_text:
            recommendations.append(f"Include primary keyword '{keyword}' in H1")

    # Image alt text
    images = re.findall(r'!\[([^\]]*)\]', draft)
    empty_alts = [i for i in images if not i.strip()]
    if empty_alts:
        issues.append(f"{len(empty_alts)} images missing alt text")
    if images:
        recommendations.append(f"Verify {len(images)} image alt texts are descriptive (30px OCR rule)")

    # Unresolved internal link placeholders (from AG·13)
    unresolved = re.findall(r'\(INTERNAL_LINK:[^)]+\)', draft)
    if unresolved:
        recommendations.append(
            f"{len(unresolved)} internal links need URLs resolved: {unresolved[:3]}"
        )

    # Check for banned words
    banned = ["delve", "tapestry", "vibrant", "foster", "leverage", "utilize",
              "furthermore", "moreover", "in conclusion"]
    found_banned = [w for w in banned if w in draft.lower()]
    if found_banned:
        issues.append(f"Banned words still present: {found_banned}")

    # External links check
    external_links = re.findall(r'\[([^\]]+)\]\(https?://[^)]+\)', draft)
    if not external_links:
        recommendations.append("Add 2-3 authoritative external links (statistics sources, official docs)")

    score = max(0, 100 - len(issues) * 15 - len(recommendations) * 5)

    return {
        "word_count": word_count,
        "h1_count": len(h1_lines),
        "h2_count": h2_count,
        "h3_count": h3_count,
        "image_count": len(images),
        "unresolved_links": len(unresolved),
        "external_links": len(external_links),
        "issues": issues,
        "recommendations": recommendations,
        "technical_score": score,
    }


def run(article_id: str, site_url: str = "") -> dict:
    keyword = get_field(article_id, "keyword")
    draft = get_field(article_id, "draft")

    print(f"[AG·10] Technical audit: '{keyword}'")

    article_audit = _audit_article_content(draft, keyword)
    site_audit = _check_site_technical(site_url)

    result = {
        "article": article_audit,
        "site": site_audit,
        "overall_score": article_audit.get("technical_score", 0),
    }

    update_state(article_id, "technical_audit", result)
    update_state(article_id, "status", "technical_done")

    warnings = article_audit["issues"][:3]

    log_agent_completion(article_id, "AG·10", {
        "output_keys": ["technical_audit"],
        "key_outputs": {
            "score": result["overall_score"],
            "word_count": article_audit["word_count"],
            "h2_count": article_audit["h2_count"],
            "issues_count": len(article_audit["issues"]),
        },
        "metrics": {"technical_score": result["overall_score"]},
        "warnings": warnings,
    })

    score = result["overall_score"]
    print(f"[AG·10] Technical score: {score}/100 | Issues: {len(article_audit['issues'])}")
    for issue in article_audit["issues"]:
        print(f"  ❌ {issue}")
    for rec in article_audit["recommendations"][:2]:
        print(f"  💡 {rec}")
    return result
