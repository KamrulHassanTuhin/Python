"""AG·05 — Brand Voice Guard: Ensures all articles in a niche share the same voice."""

import anthropic
import json
from tools.json_helper import extract_json
import os
from config import ANTHROPIC_API_KEY
from shared_memory.memory import update_state, get_field, log_agent_completion
from prompts.sop_prompts import VOICE_GUARD_SOP

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


NICHE_PRESETS = {
    "ai tools": {
        "tone": "conversational-technical",
        "vocabulary": "mid-level tech — assume reader knows what ChatGPT is but not RAG",
        "sentence_style": "short punchy sentences, data-backed claims, skeptical of hype",
        "avoid": "buzzwords, unsubstantiated superlatives, marketing speak",
        "persona": "pragmatic practitioner who has tested these tools, not a fanboy",
    },
    "finance": {
        "tone": "authoritative but accessible",
        "vocabulary": "financial terms explained on first use, no jargon without definition",
        "sentence_style": "precise, numbers-first, cite sources for all claims",
        "avoid": "get-rich-quick framing, vague promises, unqualified advice",
        "persona": "experienced financial writer who respects reader intelligence",
    },
    "health": {
        "tone": "empathetic and evidence-based",
        "vocabulary": "plain language, medical terms always explained",
        "sentence_style": "clear, reassuring, cite studies with years",
        "avoid": "fear-mongering, miracle claims, advice without medical caveat",
        "persona": "health educator who cites research and recommends consulting a doctor",
    },
    "marketing": {
        "tone": "energetic, results-focused",
        "vocabulary": "marketing native terms OK, explain niche jargon",
        "sentence_style": "action-oriented, examples with real numbers, case studies",
        "avoid": "vague platitudes, strategy without tactics, theory without proof",
        "persona": "growth practitioner who has run campaigns and shares real results",
    },
    "software": {
        "tone": "technical and direct",
        "vocabulary": "developer-level, assume coding knowledge",
        "sentence_style": "step-by-step, code-first, minimal prose padding",
        "avoid": "hand-wavy explanations, missing edge cases, outdated syntax",
        "persona": "senior engineer who values correctness and efficiency",
    },
    "general": {
        "tone": "clear and helpful",
        "vocabulary": "plain English, explain all technical terms",
        "sentence_style": "readable, varied sentence length, examples-driven",
        "avoid": "jargon without explanation, passive voice overuse",
        "persona": "knowledgeable generalist writing for an educated non-expert",
    },
}


def _get_or_create_voice_profile(article_id: str, draft: str, niche: str) -> dict:
    """Load existing voice profile for niche, or create from preset + first article."""
    profile_file = f"shared_memory/voice_profile_{niche.lower().replace(' ', '_')}.json"

    if os.path.exists(profile_file):
        with open(profile_file) as f:
            return json.load(f)

    # Find matching preset (exact or partial match)
    niche_lower = niche.lower()
    preset = None
    for key, val in NICHE_PRESETS.items():
        if key in niche_lower or niche_lower in key:
            preset = val
            break
    if preset is None:
        preset = NICHE_PRESETS["general"]

    profile = {
        "niche": niche,
        "benchmark_excerpt": draft[:600],
        "created_from_article": article_id,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "is_benchmark": True,
        **preset,
    }
    os.makedirs("shared_memory", exist_ok=True)
    with open(profile_file, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"[AG·05] New voice profile created for niche: '{niche}' (preset: {preset.get('tone')})")
    return profile


def run(article_id: str) -> dict:
    draft = get_field(article_id, "draft")
    niche = get_field(article_id, "niche")

    print(f"[AG·05] Voice check for niche: '{niche}'")

    voice_profile = _get_or_create_voice_profile(article_id, draft, niche)
    is_benchmark = voice_profile.get("is_benchmark", False)

    if is_benchmark:
        # First article — this IS the voice. Just confirm and log.
        result = {
            "consistent": True,
            "score": 100,
            "is_benchmark": True,
            "tone_detected": "establishing benchmark",
            "issues": [],
            "suggestions": [],
        }
        update_state(article_id, "voice_check", result)
        print(f"[AG·05] First article for niche — voice benchmark set.")
        log_agent_completion(article_id, "AG·05", {
            "output_keys": ["voice_check"],
            "key_outputs": {"score": 100, "is_benchmark": True},
            "metrics": {"voice_score": 100},
        })
        return result

    prompt = f"""
{VOICE_GUARD_SOP}

NICHE: {niche}
EXPECTED TONE: {voice_profile.get("tone", "clear and helpful")}
EXPECTED VOCABULARY: {voice_profile.get("vocabulary", "plain English")}
EXPECTED SENTENCE STYLE: {voice_profile.get("sentence_style", "readable")}
AVOID: {voice_profile.get("avoid", "jargon without explanation")}
PERSONA: {voice_profile.get("persona", "knowledgeable generalist")}

BENCHMARK EXCERPT (first article in this niche):
{voice_profile.get("benchmark_excerpt", "")}

ARTICLE TO CHECK:
{draft[:3500]}

Evaluate voice consistency across these dimensions:
1. Tone — matches expected tone for this niche?
2. Sentence structure — matches expected style?
3. Vocabulary level — right register for target reader?
4. Persona — sounds like the expected persona?
5. Banned patterns — any of the "avoid" items present?

Return JSON:
{{
    "consistent": true/false,
    "score": 0-100,
    "tone_detected": "formal|casual|technical|conversational",
    "issues": ["specific inconsistency 1", "specific inconsistency 2"],
    "suggestions": ["how to fix 1", "how to fix 2"]
}}
"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    result = extract_json(raw, default={"consistent": True, "score": 75, "issues": [], "suggestions": []})

    update_state(article_id, "voice_check", result)

    score = result.get("score", 0)

    log_agent_completion(article_id, "AG·05", {
        "output_keys": ["voice_check"],
        "key_outputs": {
            "score": score,
            "consistent": result.get("consistent"),
            "tone": result.get("tone_detected"),
        },
        "metrics": {"voice_score": score},
        "warnings": result.get("issues", [])[:3],
    })

    print(f"[AG·05] Voice score: {score}/100 | Consistent: {result.get('consistent')}")
    return result
