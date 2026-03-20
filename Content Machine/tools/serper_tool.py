"""Serper.dev tool — Google SERP data: search, PAA, top URLs."""

import requests
from config import SERPER_API_KEY


def google_search(query: str, num: int = 10) -> dict:
    """Run a Google search and return full SERP data."""
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "num": num}
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def get_paa(query: str) -> list[str]:
    """Get People Also Ask questions for a query."""
    data = google_search(query)
    paa = data.get("peopleAlsoAsk", [])
    return [item.get("question", "") for item in paa if item.get("question")]


def get_top_urls(query: str, num: int = 10) -> list[str]:
    """Get top organic result URLs for a query."""
    data = google_search(query, num=num)
    organic = data.get("organic", [])
    return [item.get("link", "") for item in organic if item.get("link")]
