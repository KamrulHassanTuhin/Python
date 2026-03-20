"""
Sapling AI tool — AI content detection.
FREE replacement for Originality.ai.
Free tier: 2000 API calls/month — sapling.ai
"""

import requests
from config import SAPLING_API_KEY


def check_ai_content(text: str) -> dict:
    """
    Detect AI-generated content using Sapling AI.
    Returns same format as old Originality.ai checker.

    score: 0-100 (100 = fully original/human, 0 = fully AI)
    """
    if not SAPLING_API_KEY or SAPLING_API_KEY == "your_sapling_key_here":
        return {
            "score": None,
            "skipped": True,
            "reason": "No Sapling API key — get free key at sapling.ai",
        }

    try:
        url = "https://api.sapling.ai/api/v1/aidetect"
        payload = {
            "key": SAPLING_API_KEY,
            "text": text[:5000],
        }
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()

        # Sapling returns: score (0.0-1.0) where 1.0 = AI-generated
        ai_probability = data.get("score", 0.0)
        human_score = round((1.0 - ai_probability) * 100, 1)

        return {
            "skipped": False,
            "score": human_score,          # 0-100, higher = more human/original
            "ai_probability": round(ai_probability * 100, 1),
            "passes": human_score >= 60,   # 60%+ human = acceptable
            "sentences": data.get("sentence_scores", [])[:3],
        }

    except Exception as e:
        return {"score": None, "skipped": True, "reason": str(e)}
