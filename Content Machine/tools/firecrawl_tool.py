"""Firecrawl tool — Scrapes full page content from competitor URLs."""

import requests
from config import FIRECRAWL_API_KEY


def scrape_url(url: str) -> str:
    """Extract full markdown content from a URL."""
    endpoint = "https://api.firecrawl.dev/v1/scrape"
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"url": url, "formats": ["markdown"]}
    r = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("data", {}).get("markdown", "")


def scrape_multiple(urls: list[str], max_urls: int = 10) -> list[dict]:
    """Scrape multiple URLs. Returns list of {url, content, success}."""
    results = []
    for url in urls[:max_urls]:
        try:
            content = scrape_url(url)
            results.append({"url": url, "content": content, "success": True})
        except Exception as e:
            results.append({"url": url, "content": "", "success": False, "error": str(e)})
    return results
