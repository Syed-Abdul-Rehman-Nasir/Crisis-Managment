from gemini_settings import generate_json
from json_utils import safe_json_dumps


async def explain_allocation(
    crisis: dict,
    allocation_plan: dict,
    population: int,
    competing_crises: list,
    gemini_client=None,
) -> dict:
    total_units = allocation_plan.get("total_deployed", 0)
    fallback_dict = {
        "headline": f"Deploying {total_units} units to {crisis.get('location', 'unknown')}",
        "rationale": f"Standard protocol allocation based on {crisis.get('severity', 'UNKNOWN')} severity.",
        "tradeoffs": "No competing crises recorded.",
        "eta_context": "Units dispatched per travel-time matrix.",
        "confidence_note": f"Classification confidence: {crisis.get('confidence', 0.0):.0%}",
    }

    prompt = f"""
You are an emergency operations commander writing a briefing for senior officials.
Be direct, specific, and quantitative. Explain resource allocation decisions as if lives depend on the clarity of your reasoning. Never use filler phrases.
Output valid JSON.

CRISIS CONTEXT:
Type: {crisis.get('type')}
Severity: {crisis.get('severity')}
Location: {crisis.get('location')}
Confidence: {crisis.get('confidence')}
Affected Population: {population}

ALLOCATION PLAN:
{safe_json_dumps(allocation_plan)}

COMPETING CRISES:
{safe_json_dumps(competing_crises)}

OUTPUT SCHEMA:
{{
  "headline": "string (one punchy sentence like an ops bulletin)",
  "rationale": "string (2-3 sentences: why this many units, why these types)",
  "tradeoffs": "string (what was deprioritized and why, especially if competing crises)",
  "eta_context": "string (what the ETA means in human terms)",
  "confidence_note": "string (note on how classification confidence affected the allocation)"
}}
"""
    result = generate_json(prompt, temperature=0.3)
    if result:
        return result
    return fallback_dict
