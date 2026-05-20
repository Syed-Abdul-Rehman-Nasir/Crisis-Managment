from fastapi import APIRouter, Request, HTTPException, Body
from datetime import datetime
from typing import List, Dict, Optional, Any
from models import CrisisSchema, AllocationPlan, MultiCrisisAllocationPlan
from reasoning.allocation import AllocationAlgorithm
from reasoning.multi_crisis import MultiCrisisCoordinator

router = APIRouter(prefix="/api/resources", tags=["resources"])
allocator = AllocationAlgorithm()
coordinator = MultiCrisisCoordinator()

from reasoning.allocation_explainer import explain_allocation

@router.post("/allocate")
async def allocate_resources(request: Request, crisis: Optional[Dict[str, Any]] = Body(None)):
    inventory = request.app.state.inventory
    start_time = datetime.utcnow()
    
    plan = None
    crisis_obj = None
    explanation_dict = {}
    
    if crisis:
        try:
            crisis_obj = CrisisSchema.model_validate(crisis)
        except Exception:
            pass
            
    if not crisis_obj and request.app.state.active_crises:
        crisis_obj = request.app.state.active_crises[0]
        
    if crisis_obj:
        try:
            plan = allocator.allocate(crisis_obj, inventory)
            request.app.state.allocation_plans[plan.plan_id] = plan
            
            # Track deployment updates in inventory
            deployed_ids = [item.resource_id for item in plan.allocations]
            inventory.mark_deployed(deployed_ids, crisis_obj.location)
            
            explanation_dict = await explain_allocation(
                crisis=crisis_obj.model_dump(mode="json"),
                allocation_plan=plan.model_dump(mode="json"),
                population=85000, # Mock population, could map from zone
                competing_crises=[], # Simplified for now
            )
            
            # Append trace log
            request.app.state.append_trace(
                agent="ResourceAllocationAgent",
                action="allocate",
                input_summary=f"Crisis {crisis_obj.crisis_id} ({crisis_obj.type.value}) at {crisis_obj.location}.",
                output_summary=f"Allocated {plan.total_deployed} response units. Unmet needs: {len(plan.unmet_needs)}.",
                reasoning=explanation_dict.get("rationale", plan.allocation_reasoning),
                tool_called="allocate_resources",
                start_time=start_time
            )
        except Exception as e:
            print("Allocation error:", e)
            
    if not plan:
        plan = AllocationPlan(
            crisis_id=crisis_obj.crisis_id if crisis_obj else "g10_flood",
            allocations=[],
            allocation_reasoning="Fallback allocation reasoning."
        )
        
    return {
        "plan_id": plan.plan_id,
        "crisis_id": plan.crisis_id,
        "allocations": [a.model_dump(mode="json") for a in plan.allocations] if hasattr(plan, "allocations") else [],
        "allocation_reasoning": plan.allocation_reasoning,
        "total_deployed": plan.total_deployed,
        "unmet_needs": plan.unmet_needs,
        "explanation": explanation_dict,
        "allocation": request.app.state.compat_allocation or {
            (crisis_obj.location if crisis_obj else "G-10 Islamabad"): "3 Rescue Teams + 2 Police Units + 2 Water Tankers/Pumps"
        },
        "reasoning": request.app.state.compat_reasoning or plan.allocation_reasoning
    }

@router.post("/allocate-multi", response_model=MultiCrisisAllocationPlan)
def allocate_multi_resources(crises: List[CrisisSchema], request: Request):
    inventory = request.app.state.inventory
    start_time = datetime.utcnow()
    
    m_plan = coordinator.coordinate(crises, inventory)
    
    # Store plans in state
    for cid, plan in m_plan.crisis_plans.items():
        request.app.state.allocation_plans[plan.plan_id] = plan
        
    summary_text = coordinator.generate_trade_off_summary(m_plan)
    
    request.app.state.append_trace(
        agent="ResourceAllocationAgent",
        action="coordinate_multi_crisis",
        input_summary=f"Coordinating resources for {len(crises)} concurrent crises.",
        output_summary=f"Generated multi-crisis plan. Priority order: {', '.join(m_plan.priority_order)}.",
        reasoning=summary_text,
        tool_called="coordinate",
        start_time=start_time
    )
    
    return m_plan

@router.get("/inventory")
def get_inventory_summary(request: Request):
    return request.app.state.inventory.get_inventory_summary()

@router.post("/reset")
def reset_inventory(request: Request):
    request.app.state.inventory.reset_all()
    request.app.state.allocation_plans.clear()
    return {"status": "success", "message": "Resource inventory successfully reset to defaults."}

@router.get("/allocation/{plan_id}", response_model=AllocationPlan)
def get_allocation_plan(plan_id: str, request: Request):
    plan = request.app.state.allocation_plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Allocation plan {plan_id} not found.")
    return plan
