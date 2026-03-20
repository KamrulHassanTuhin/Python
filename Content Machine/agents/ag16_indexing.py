"""AG·16 — Indexing & Distribution: Saves locally, pings IndexNow, updates sitemap, stores in Supabase."""

import requests
import json
import os
from datetime import datetime
from shared_memory.memory import update_state, get_field, log_agent_completion
from config import SUPABASE_URL, SUPABASE_KEY, INDEXNOW_KEY, SITE_URL


def _ping_indexnow(url: str, api_key: str, host: str) -> dict:
    """Notify Bing/Yandex/Seznam via IndexNow API."""
    endpoint = "https://api.indexnow.org/indexnow"
    payload = {
        "host": host,
        "key": api_key,
        "keyLocation": f"https://{host}/{api_key}.txt",
        "urlList": [url],
    }
    try:
        r = requests.post(endpoint, json=payload, timeout=10)
        return {"status": r.status_code, "success": r.status_code in [200, 202]}
    except Exception as e:
        return {"status": "error", "error": str(e), "success": False}


def _update_sitemap_entry(output_dir: str, article_url: str, changefreq: str) -> bool:
    """Append new URL entry to sitemap_entries.xml file."""
    sitemap_path = os.path.join(output_dir, "sitemap_entries.xml")
    today = datetime.now().strftime("%Y-%m-%d")
    entry = (
        f"  <url>\n"
        f"    <loc>{article_url}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>0.8</priority>\n"
        f"  </url>"
    )
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(sitemap_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
        return True
    except Exception:
        return False


def _save_to_supabase(article_id: str, keyword: str, output_path: str, quality_score: int, draft: str) -> dict:
    """Save article metadata to Supabase articles table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"success": False, "note": "Supabase not configured"}
    try:
        url = f"{SUPABASE_URL}/rest/v1/articles"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        payload = {
            "article_id": article_id,
            "keyword": keyword,
            "output_path": output_path,
            "quality_score": quality_score,
            "word_count": len(draft.split()),
            "published_at": datetime.now().isoformat(),
            "status": "published",
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code in [200, 201]:
            return {"success": True}
        return {"success": False, "status": r.status_code, "note": r.text[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run(
    article_id: str,
    output_path: str = "",
    site_url: str = "",
    indexnow_key: str = "",
) -> dict:
    # Auto-read from config if not passed explicitly
    if not indexnow_key:
        indexnow_key = INDEXNOW_KEY
    if not site_url:
        site_url = SITE_URL
    keyword = get_field(article_id, "keyword")
    freshness = get_field(article_id, "freshness_schedule") or {}
    quality_score = (get_field(article_id, "quality_result") or {}).get("total", 0)
    draft = get_field(article_id, "draft") or ""

    print(f"[AG·16] Indexing & distribution: '{keyword}'")

    # Use freshness schedule from AG·14 for sitemap changefreq
    changefreq = {
        "monthly": "monthly",
        "quarterly": "monthly",
        "bi-annual": "yearly",
    }.get(freshness.get("niche_frequency", "quarterly"), "monthly")

    results = {
        "timestamp": datetime.now().isoformat(),
        "keyword": keyword,
        "actions": [],
    }

    # 1. Local file already saved by main.py — log it
    if output_path:
        results["actions"].append({
            "action": "local_save",
            "success": os.path.exists(output_path),
            "path": output_path,
        })
        exists = os.path.exists(output_path)
        print(f"[AG·16] Local file: {'✅' if exists else '❌'} {output_path}")

    # 2. IndexNow ping (Bing + Yandex + Seznam)
    if indexnow_key and site_url:
        slug = keyword.lower().replace(" ", "-")
        article_url = f"{site_url.rstrip('/')}/{slug}/"
        host = site_url.replace("https://", "").replace("http://", "").rstrip("/")
        ping = _ping_indexnow(article_url, indexnow_key, host)
        results["article_url"] = article_url
        results["actions"].append({"action": "indexnow_ping", "url": article_url, **ping})
        print(f"[AG·16] IndexNow ping: {'✅' if ping.get('success') else '❌'} status={ping.get('status')}")

        # 3. Sitemap update
        output_dir = os.path.dirname(output_path) if output_path else "output"
        sitemap_ok = _update_sitemap_entry(output_dir, article_url, changefreq)
        results["actions"].append({
            "action": "sitemap_update",
            "success": sitemap_ok,
            "changefreq": changefreq,
        })
        print(f"[AG·16] Sitemap: {'✅' if sitemap_ok else '❌'} changefreq={changefreq}")
    else:
        results["actions"].append({
            "action": "indexnow_ping",
            "success": False,
            "note": "Add INDEXNOW_KEY + SITE_URL to .env to enable automatic indexing",
        })
        print("[AG·16] IndexNow skipped — add INDEXNOW_KEY + SITE_URL to .env")

    # 4. Supabase storage
    supabase_result = _save_to_supabase(article_id, keyword, output_path, quality_score, draft)
    results["actions"].append({"action": "supabase_save", **supabase_result})
    if supabase_result.get("success"):
        print(f"[AG·16] Supabase: ✅ article saved to database")
    elif supabase_result.get("note") and "not configured" in supabase_result.get("note", ""):
        print(f"[AG·16] Supabase: skipped (not configured)")
    else:
        print(f"[AG·16] Supabase: ⚠ {supabase_result.get('note') or supabase_result.get('error', 'failed')}")

    update_state(article_id, "distribution", results)
    update_state(article_id, "status", "distributed")

    successful = sum(1 for a in results["actions"] if a.get("success"))

    log_agent_completion(article_id, "AG·16", {
        "output_keys": ["distribution"],
        "key_outputs": {
            "actions_taken": len(results["actions"]),
            "successful": successful,
            "changefreq": changefreq,
        },
        "metrics": {"distribution_success": successful},
    })

    print(f"[AG·16] Distribution: {successful}/{len(results['actions'])} successful")
    return results
