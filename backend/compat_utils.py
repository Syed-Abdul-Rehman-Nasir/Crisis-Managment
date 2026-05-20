"""Helpers to build UI-facing compat crisis cards with coordinates."""

from typing import Any, Dict, Optional

from models import CrisisSchema, CrisisType

# Canonical coordinates for demo locations (WGS84)
GEO = {
    "g10": (33.6938, 73.0652),
    "gulberg_lahore": (31.5204, 74.3587),
    "islamabad": (33.6844, 73.0479),
    "lahore": (31.5204, 74.3587),
    "karachi": (24.8607, 67.0011),
    "quetta": (30.1798, 66.9750),
}


def _type_label(crisis_type) -> str:
    if isinstance(crisis_type, CrisisType):
        if crisis_type == CrisisType.FLOOD:
            return "Urban Flooding"
        return crisis_type.value.replace("_", " ").title()
    if isinstance(crisis_type, str):
        if crisis_type.lower() == "flood":
            return "Urban Flooding"
        return crisis_type.replace("_", " ").title()
    return "Unknown"


def _severity_label(severity) -> str:
    if hasattr(severity, "value"):
        return severity.value.upper()
    return str(severity).upper() if severity else "MEDIUM"


def crisis_schema_to_compat_card(crisis: CrisisSchema, **overrides: Any) -> Dict[str, Any]:
    card = {
        "id": crisis.crisis_id,
        "type": _type_label(crisis.type),
        "location": crisis.location,
        "severity": _severity_label(crisis.severity),
        "confidence": crisis.confidence,
        "time_detected": "Just now",
        "radius_km": crisis.affected_radius_km,
        "latitude": crisis.latitude,
        "longitude": crisis.longitude,
    }
    card.update(overrides)
    return card


def crisis_dict_to_compat_card(crisis: dict, **overrides: Any) -> Dict[str, Any]:
    ctype = crisis.get("type")
    if hasattr(ctype, "value"):
        type_label = _type_label(ctype)
    elif isinstance(ctype, str):
        type_label = _type_label(ctype)
    else:
        type_label = "Unknown"

    sev = crisis.get("severity")
    if hasattr(sev, "value"):
        severity_label = sev.value.upper()
    elif isinstance(sev, str):
        severity_label = sev.upper()
    else:
        severity_label = "MEDIUM"

    card = {
        "id": crisis.get("crisis_id", crisis.get("id", "crisis")),
        "type": type_label,
        "location": crisis.get("location", "Unknown"),
        "severity": severity_label,
        "confidence": crisis.get("confidence", 0.0),
        "time_detected": crisis.get("time_detected", "Just now"),
        "radius_km": crisis.get("affected_radius_km", crisis.get("radius_km", 1.0)),
        "latitude": crisis.get("latitude", GEO["islamabad"][0]),
        "longitude": crisis.get("longitude", GEO["islamabad"][1]),
    }
    card.update(overrides)
    return card
