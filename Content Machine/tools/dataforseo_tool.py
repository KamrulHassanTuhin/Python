"""DataForSEO tool — Keyword volume, difficulty, and SERP overview data."""

import requests
import base64
from config import DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD


def _auth_header() -> dict:
    """Build Basic Auth header for DataForSEO API."""
    creds = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    encoded = base64.b64encode(creds.encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


def get_keyword_volume(keywords: list[str], location_code: int = 2840) -> list[dict]:
    """
    Get monthly search volume for a list of keywords.
    location_code 2840 = United States.
    """
    url = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
    payload = [{"keywords": keywords, "location_code": location_code, "language_code": "en"}]
    r = requests.post(url, headers=_auth_header(), json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = data.get("tasks", [{}])[0].get("result", [])
    return results or []


def get_serp_overview(keyword: str, location_code: int = 2840) -> dict:
    """Get SERP overview: top pages, featured snippets, difficulty."""
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = [{
        "keyword": keyword,
        "location_code": location_code,
        "language_code": "en",
        "depth": 10,
    }]
    r = requests.post(url, headers=_auth_header(), json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("tasks", [{}])[0].get("result", [{}])[0] or {}
