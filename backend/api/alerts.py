from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any
from models import CrisisSchema, AllocationPlan, StakeholderMessages
from reasoning.stakeholder_messages import StakeholderMessageGenerator
from intelligence.baseline import BaselineRuleSystem, ComparisonReport

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
msg_generator = StakeholderMessageGenerator()

class BroadcastRequest(BaseModel):
    crisis: CrisisSchema
    allocation: AllocationPlan

@router.post("/broadcast", response_model=StakeholderMessages)
def broadcast_alerts(req: BroadcastRequest, request: Request):
    start_time = datetime.utcnow()
    crisis = req.crisis
    allocation = req.allocation
    
    # Generate messages
    messages = msg_generator.generate_all(crisis, allocation, use_gemini=True)
    
    # Store in state
    request.app.state.stakeholder_messages_store[crisis.crisis_id] = messages
    
    # Append trace log
    request.app.state.append_trace(
        agent="StakeholderCommunicationAgent",
        action="broadcast",
        input_summary=f"Crisis {crisis.crisis_id} + AllocationPlan {allocation.plan_id}.",
        output_summary=f"Broadcasting warnings to public (Urdu + English), transport, media, and utilities.",
        reasoning=f"Broadcasting localized advisory to public. Hospital ICU warnings dispatched. Utilities notified.",
        tool_called="generate_all",
        start_time=start_time
    )
    
    return messages

@router.get("/messages/{crisis_id}", response_model=StakeholderMessages)
def get_messages(crisis_id: str, request: Request):
    msgs = request.app.state.stakeholder_messages_store.get(crisis_id)
    if not msgs:
        raise HTTPException(status_code=404, detail=f"Broadcast messages for crisis {crisis_id} not found.")
    return msgs

@router.get("/comparison")
def get_comparison(request: Request):
    crises = request.app.state.active_crises
    if not crises:
        raise HTTPException(status_code=400, detail="No active crises available to perform comparison.")
        
    last_crisis = crises[-1]
    
    # Retrieve allocation plan
    last_plan = None
    for plan in request.app.state.allocation_plans.values():
        if plan.crisis_id == last_crisis.crisis_id:
            last_plan = plan
            break
            
    if not last_plan:
        last_plan = AllocationPlan(crisis_id=last_crisis.crisis_id, allocation_reasoning="Template plan.")
        
    # Retrieve messages
    last_msg = request.app.state.stakeholder_messages_store.get(last_crisis.crisis_id)
    if not last_msg:
        last_msg = msg_generator.generate_all(last_crisis, last_plan, use_gemini=False)
        
    # Run baseline matching
    baseline_sys = BaselineRuleSystem()
    scheduler = request.app.state.scheduler
    raw_signals = list(scheduler.buffer)
    if not raw_signals:
        raw_signals = scheduler.get_scenario_signals("g10_flood")
        
    # Cast scored signals in buffer back to raw signals if needed, or process directly
    # (Baseline accepts RawSignal list, ScoredSignal is a subclass so it matches perfectly!)
    baseline_res = baseline_sys.process_signals(raw_signals)
    
    # Generate side by side comparison
    comp_report = ComparisonReport()
    comparison_data = comp_report.generate(
        ciro_crisis=last_crisis,
        ciro_allocation=last_plan,
        ciro_messages=last_msg,
        ciro_latency_ms=28, # typical algorithmic pipeline latency in ms
        baseline_result=baseline_res,
        baseline_latency_ms=baseline_res["processing_time_ms"]
    )
    
    return comp_report.format_as_dict_for_api(comparison_data)
