"""
Tavily AI tool — Real-time search with citations.
FREE replacement for Perplexity API.
Free tier: 1000 API calls/month — tavily.com
"""

import requests
from config import TAVILY_API_KEY


def get_facts(query: str) -> dict:
    """
    Fetch real-time facts with source citations using Tavily.
    Returns same format as the old Perplexity tool so no other code changes needed.
    """
    if not TAVILY_API_KEY or TAVILY_API_KEY == "your_tavily_key_here":
        print("[Tavily] No API key — skipping real-time facts.")
        return {"answer": "", "citations": []}

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": False,
        "max_results": 8,
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()

        # Build answer from Tavily's direct answer + result snippets
        answer = data.get("answer", "")

        results = data.get("results", [])
        if not answer and results:
            # Fallback: combine top result snippets
            snippets = [r.get("content", "")[:300] for r in results[:3]]
            answer = " ".join(snippets)

        # Citations = source URLs
        citations = [r.get("url", "") for r in results if r.get("url")]

        return {"answer": answer, "citations": citations}

    except Exception as e:
        print(f"[Tavily] Error: {e}")
        return {"answer": "", "citations": []}
