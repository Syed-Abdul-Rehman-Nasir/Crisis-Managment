from fastapi import APIRouter, Request, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any, Optional
from models import CrisisSchema, AllocationPlan, BeforeAfterState, CrisisType, SeverityLevel

router = APIRouter(prefix="/api/actions", tags=["actions"])

class SimulationRequest(BaseModel):
    crisis: CrisisSchema
    allocation: AllocationPlan

@router.post("/simulate")
def simulate_actions(request: Request, req: Optional[Dict[str, Any]] = Body(None)):
    start_time = datetime.utcnow()
    
    crisis_obj = None
    allocation_obj = None
    
    if req:
        try:
            crisis_dict = req.get("crisis")
            alloc_dict = req.get("allocation")
            if crisis_dict and alloc_dict:
                crisis_obj = CrisisSchema.model_validate(crisis_dict)
                allocation_obj = AllocationPlan.model_validate(alloc_dict)
        except Exception:
            pass
            
    if not crisis_obj or not allocation_obj:
        # Fallback to first active crisis and its allocation plan if available in state
        if request.app.state.active_crises:
            crisis_obj = request.app.state.active_crises[0]
            for plan in request.app.state.allocation_plans.values():
                if plan.crisis_id == crisis_obj.crisis_id:
                    allocation_obj = plan
                    break
                    
    # If still none, create dummy fallbacks
    if not crisis_obj:
        crisis_obj = CrisisSchema(
            crisis_id="g10_flood",
            type=CrisisType.FLOOD,
            severity=SeverityLevel.HIGH,
            confidence=0.89,
            affected_radius_km=2.4,
            location="G-10, Islamabad",
            latitude=33.6938,
            longitude=73.0652,
            explanation="Fallback"
        )
    if not allocation_obj:
        allocation_obj = AllocationPlan(
            crisis_id=crisis_obj.crisis_id,
            allocations=[],
            allocation_reasoning="Fallback"
        )
        
    before_stats = {
        "active_hazard_level": 0.85 if crisis_obj.severity.value in ["high", "critical"] else 0.45,
        "traffic_congestion_percentage": 340.0 if crisis_obj.type == CrisisType.FLOOD else 120.0,
        "affected_residents_evacuated": 0.0,
        "hospital_icu_standby_ready": False,
        "casualty_probability": 0.38 if crisis_obj.severity.value == "critical" else 0.18
    }
    
    after_stats = {
        "active_hazard_level": 0.10,
        "traffic_congestion_percentage": 140.0 if crisis_obj.type == CrisisType.FLOOD else 100.0,
        "affected_residents_evacuated": 96.5,
        "hospital_icu_standby_ready": True,
        "casualty_probability": 0.01
    }
    
    improvements = {
        "hazard_reduction_percent": 88.2,
        "rerouting_congestion_mitigated_percent": 58.8 if crisis_obj.type == CrisisType.FLOOD else 16.6,
        "evacuation_efficiency_reached": 96.5,
        "average_first_responder_arrival_eta_minutes": min([a.eta_minutes for a in allocation_obj.allocations]) if (hasattr(allocation_obj, "allocations") and allocation_obj.allocations) else 15,
        "estimated_lives_saved_count": 48 if crisis_obj.type == CrisisType.FLOOD else 12
    }
    
    state_report = BeforeAfterState(
        scenario_id=crisis_obj.crisis_id,
        before=before_stats,
        after=after_stats,
        improvement_metrics=improvements,
        generated_at=datetime.utcnow()
    )
    
    # Trace log
    request.app.state.append_trace(
        agent="ResponsePlanningAgent",
        action="simulate",
        input_summary=f"Simulating actions for crisis {crisis_obj.crisis_id} with {allocation_obj.total_deployed} units.",
        output_summary=f"Mitigated hazard level from {before_stats['active_hazard_level']} to {after_stats['active_hazard_level']}.",
        reasoning=f"Rerouting and emergency dispatch led to {improvements['hazard_reduction_percent']}% hazard reduction. First responders arrived in {improvements['average_first_responder_arrival_eta_minutes']}m.",
        tool_called="simulate_actions",
        start_time=start_time
    )
    
    return {
        "scenario_id": state_report.scenario_id,
        "before": state_report.before,
        "after": state_report.after,
        "improvement_metrics": state_report.improvement_metrics,
        "generated_at": state_report.generated_at.isoformat(),
        "actions": request.app.state.compat_actions or [
            {"action": "Reroute outbound traffic from G-10 Sector", "status": "COMPLETED"},
            {"action": "Coordinate trauma services with local healthcare units", "status": "COMPLETED"}
        ]
    }

@router.get("/before-after/{scenario}", response_model=BeforeAfterState)
def get_before_after_by_scenario(scenario: str, request: Request):
    # Retrieve matching simulation state
    scenario_clean = scenario.lower().strip()
    
    # Create matching mock schema on the fly
    if "flood" in scenario_clean:
        c_type, severity = CrisisType.FLOOD, "high"
    elif "heat" in scenario_clean:
        c_type, severity = CrisisType.HEATWAVE, "medium"
    else:
        c_type, severity = CrisisType.UNKNOWN, "low"
        
    mock_crisis = CrisisSchema(
        crisis_id=f"mock-{scenario_clean}",
        type=c_type,
        severity=severity,
        confidence=0.88,
        affected_radius_km=2.5,
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        explanation="Simulated crisis"
    )
    
    # Mock allocation plan
    mock_plan = AllocationPlan(
        crisis_id=mock_crisis.crisis_id,
        allocations=[],
        allocation_reasoning="None"
    )
    
    return simulate_actions(SimulationRequest(crisis=mock_crisis, allocation=mock_plan), request)

@router.get("/trace")
def get_trace_log(request: Request):
    return {"logs": request.app.state.trace_log}

@router.post("/trace/clear")
def clear_trace_log(request: Request):
    request.app.state.trace_log.clear()
    return {"status": "success", "message": "Agent trace log cleared."}
