from enum import Enum
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class SignalSource(str, Enum):
    SOCIAL_MEDIA = "social_media"
    WEATHER_API = "weather_api"
    GOOGLE_MAPS = "google_maps"
    EMERGENCY_CALL = "emergency_call"
    HISTORICAL_DATA = "historical_data"

class RawSignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: SignalSource
    content: str
    location: str
    latitude: float = Field(..., ge=23.0, le=37.0)
    longitude: float = Field(..., ge=60.0, le=78.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    recency_minutes: int = Field(..., ge=0, le=1440)
    mention_frequency: int = Field(..., ge=1, le=500)
    geo_precision: float = Field(..., ge=0.0, le=1.0)
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "signal_id": "8b9a2c34-5678-90ab-cdef-1234567890ab",
                "source_type": "social_media",
                "content": "G-10/3 mein pani bhar gaya hai, gali number 4 band ho gayi. Koi rescue nahin aaya abhi tak!",
                "location": "G-10, Islamabad",
                "latitude": 33.6938,
                "longitude": 73.0652,
                "timestamp": "2026-05-20T12:00:00Z",
                "recency_minutes": 10,
                "mention_frequency": 5,
                "geo_precision": 0.85,
                "raw_metadata": {}
            }
        }

class ScoredSignal(RawSignal):
    credibility_score: float = Field(..., ge=0.0, le=1.0)
    credibility_explanation: Dict[str, Any]

class SignalBatch(BaseModel):
    batch_id: str = Field(default_factory=lambda: str(uuid4()))
    signals: List[ScoredSignal]
    batch_timestamp: datetime = Field(default_factory=datetime.utcnow)
    scenario_tag: Optional[str] = None
    reasoning_log: List[str] = Field(default_factory=list)
