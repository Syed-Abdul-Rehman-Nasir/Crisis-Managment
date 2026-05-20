from gemini_settings import generate_json
from json_utils import safe_json_dumps


async def fuse_signals_with_gemini(
    scored_signals: list[dict],
    classifier_result: dict,
    gemini_client=None,
) -> dict:
    fallback_dict = {
        "gemini_reasoning": "Signal fusion unavailable — using baseline classifier",
        "uncertainty_level": "MEDIUM",
        "coherence_score": classifier_result.get("confidence", 0.0),
        "contradiction_flags": [],
        "adjusted_confidence": classifier_result.get("confidence", 0.0),
        "source_weight_summary": "Baseline keyword classifier used",
    }

    prompt = f"""
You are a crisis intelligence analyst. You receive scored sensor signals and a preliminary classification. Your job is to reason about signal coherence, contradiction, and confidence. Be concise and technical.
Always output valid JSON matching the exact schema provided.

SCORED SIGNALS:
{safe_json_dumps(scored_signals)}

PRELIMINARY CLASSIFICATION:
{safe_json_dumps(classifier_result)}

OUTPUT SCHEMA:
{{
  "gemini_reasoning": "string (3-4 sentences explaining the classification)",
  "uncertainty_level": "string (LOW, MEDIUM, or HIGH)",
  "coherence_score": "float (0.0-1.0, how consistent are the signals?)",
  "contradiction_flags": ["string (list of strings describing any conflicts)"],
  "adjusted_confidence": "float (Gemini's final confidence 0.0-1.0)",
  "source_weight_summary": "string (one sentence on which sources drove the verdict)"
}}
"""
    result = generate_json(prompt, temperature=0.2)
    if result:
        return result
    return fallback_dict
