from enum import Enum
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class CrisisType(str, Enum):
    FLOOD = "flood"
    HEATWAVE = "heatwave"
    ACCIDENT = "accident"
    INFRASTRUCTURE = "infrastructure"
    FIRE = "fire"
    EARTHQUAKE = "earthquake"
    UNKNOWN = "unknown"

class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

SEVERITY_SCORES: Dict[SeverityLevel, int] = {
    SeverityLevel.LOW: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.HIGH: 3,
    SeverityLevel.CRITICAL: 4,
}

def get_severity_score(level: SeverityLevel) -> int:
    """Module-level helper. Use this instead of a method on the enum."""
    return SEVERITY_SCORES[level]

class CrisisSchema(BaseModel):
    crisis_id: str = Field(default_factory=lambda: str(uuid4()))
    type: CrisisType
    severity: SeverityLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    affected_radius_km: float = Field(..., ge=0.0)
    location: str
    latitude: float = Field(..., ge=23.0, le=37.0)
    longitude: float = Field(..., ge=60.0, le=78.0)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    explanation: str
    contributing_signals: List[str] = Field(default_factory=list)
    is_active: bool = True
    retracted: bool = False
    retraction_reason: Optional[str] = None
    reasoning_log: List[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "crisis_id": "9b8a7c65-4321-0fed-cba9-876543210fed",
                "type": "flood",
                "severity": "high",
                "confidence": 0.89,
                "affected_radius_km": 2.4,
                "location": "G-10, Islamabad",
                "latitude": 33.6938,
                "longitude": 73.0652,
                "detected_at": "2026-05-20T12:00:00Z",
                "explanation": "Urban flooding detected at G-10 Islamabad due to heavy precipitation (87.3mm in the last hour).",
                "contributing_signals": ["sig-1", "sig-2"],
                "is_active": True,
                "retracted": False,
                "retraction_reason": None,
                "reasoning_log": ["ClassificationAgent completed classification."]
            }
        }

class FalsePositiveResult(BaseModel):
    original_crisis_id: str
    contradiction_score: float = Field(..., ge=0.0, le=1.0)
    retract: bool
    correction: str
    corrected_type: Optional[CrisisType] = None
    log_entry: str
    correction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    verification_log: List[str] = Field(default_factory=list)
