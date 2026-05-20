from enum import Enum
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ResourceType(str, Enum):
    AMBULANCE = "ambulance"
    POLICE_UNIT = "police_unit"
    RESCUE_TEAM = "rescue_team"
    WATER_TANKER = "water_tanker"
    MEDICAL_OUTREACH = "medical_outreach"
    FIRE_ENGINE = "fire_engine"

class ResourceStatus(str, Enum):
    AVAILABLE = "available"
    DEPLOYED = "deployed"
    EN_ROUTE = "en_route"
    UNAVAILABLE = "unavailable"

class Resource(BaseModel):
    resource_id: str = Field(default_factory=lambda: str(uuid4()))
    type: ResourceType
    status: ResourceStatus = ResourceStatus.AVAILABLE
    current_location: str
    current_lat: float
    current_lng: float
    travel_time_by_zone: Dict[str, int] = Field(default_factory=dict)
    unit_name: str
    capacity: int

    class Config:
        populate_by_name = True

class AllocationItem(BaseModel):
    resource_id: str
    resource_type: ResourceType
    unit_name: str
    destination: str
    eta_minutes: int
    reasoning: str

    class Config:
        populate_by_name = True

class AllocationPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    crisis_id: str
    allocations: List[AllocationItem] = Field(default_factory=list)
    unmet_needs: List[str] = Field(default_factory=list)
    total_deployed: int = 0
    allocation_reasoning: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

class MultiCrisisAllocationPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    crisis_plans: Dict[str, AllocationPlan] = Field(default_factory=dict)
    conflict_resolution_log: List[str] = Field(default_factory=list)
    priority_order: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

class StakeholderMessages(BaseModel):
    crisis_id: str
    public_urdu: str
    public_english: str
    hospital_request: str
    utility_alert: str
    transport_rerouting: str
    media_briefing: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

class BeforeAfterState(BaseModel):
    scenario_id: str
    before: Dict[str, Any]
    after: Dict[str, Any]
    improvement_metrics: Dict[str, Any]
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
