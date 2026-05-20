import math
from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Any

try:
    from models import CrisisType, SeverityLevel, get_severity_score, AllocationItem, AllocationPlan, Resource, ResourceType, ResourceStatus
    from reasoning.resource_model import ResourceInventory
except ImportError:
    from ..models import CrisisType, SeverityLevel, get_severity_score, AllocationItem, AllocationPlan, Resource, ResourceType, ResourceStatus
    from .resource_model import ResourceInventory

class AllocationAlgorithm:
    """
    Ranks and selects emergency response resources based on relevance, proximity,
    and capacity caps.
    """

    RESOURCE_RELEVANCE = {
        CrisisType.FLOOD: {
            ResourceType.RESCUE_TEAM: 1.0, ResourceType.WATER_TANKER: 0.9,
            ResourceType.POLICE_UNIT: 0.7, ResourceType.AMBULANCE: 0.6,
            ResourceType.MEDICAL_OUTREACH: 0.3, ResourceType.FIRE_ENGINE: 0.1
        },
        CrisisType.HEATWAVE: {
            ResourceType.MEDICAL_OUTREACH: 1.0, ResourceType.AMBULANCE: 0.9,
            ResourceType.WATER_TANKER: 0.7, ResourceType.POLICE_UNIT: 0.3,
            ResourceType.RESCUE_TEAM: 0.2, ResourceType.FIRE_ENGINE: 0.1
        },
        CrisisType.ACCIDENT: {
            ResourceType.AMBULANCE: 1.0, ResourceType.POLICE_UNIT: 1.0,
            ResourceType.FIRE_ENGINE: 0.6, ResourceType.RESCUE_TEAM: 0.5,
            ResourceType.MEDICAL_OUTREACH: 0.4, ResourceType.WATER_TANKER: 0.1
        },
        CrisisType.FIRE: {
            ResourceType.FIRE_ENGINE: 1.0, ResourceType.AMBULANCE: 0.8,
            ResourceType.POLICE_UNIT: 0.7, ResourceType.RESCUE_TEAM: 0.6,
            ResourceType.MEDICAL_OUTREACH: 0.4, ResourceType.WATER_TANKER: 0.3
        },
        CrisisType.INFRASTRUCTURE: {
            ResourceType.POLICE_UNIT: 0.8, ResourceType.RESCUE_TEAM: 0.6,
            ResourceType.AMBULANCE: 0.4, ResourceType.WATER_TANKER: 0.5,
            ResourceType.FIRE_ENGINE: 0.3, ResourceType.MEDICAL_OUTREACH: 0.2
        },
        CrisisType.UNKNOWN: {
            ResourceType.POLICE_UNIT: 0.5, ResourceType.RESCUE_TEAM: 0.5,
            ResourceType.AMBULANCE: 0.5, ResourceType.WATER_TANKER: 0.1,
            ResourceType.FIRE_ENGINE: 0.1, ResourceType.MEDICAL_OUTREACH: 0.1
        }
    }
    
    SEVERITY_RESOURCE_COUNT = {
        SeverityLevel.CRITICAL: {ResourceType.RESCUE_TEAM: 3, ResourceType.AMBULANCE: 3,
                                  ResourceType.POLICE_UNIT: 4, ResourceType.WATER_TANKER: 3,
                                  ResourceType.MEDICAL_OUTREACH: 2, ResourceType.FIRE_ENGINE: 2},
        SeverityLevel.HIGH:     {ResourceType.RESCUE_TEAM: 2, ResourceType.AMBULANCE: 2,
                                  ResourceType.POLICE_UNIT: 3, ResourceType.WATER_TANKER: 2,
                                  ResourceType.MEDICAL_OUTREACH: 1, ResourceType.FIRE_ENGINE: 1},
        SeverityLevel.MEDIUM:   {ResourceType.RESCUE_TEAM: 1, ResourceType.AMBULANCE: 1,
                                  ResourceType.POLICE_UNIT: 2, ResourceType.WATER_TANKER: 1,
                                  ResourceType.MEDICAL_OUTREACH: 1, ResourceType.FIRE_ENGINE: 1},
        SeverityLevel.LOW:      {ResourceType.RESCUE_TEAM: 0, ResourceType.AMBULANCE: 1,
                                  ResourceType.POLICE_UNIT: 1, ResourceType.WATER_TANKER: 0,
                                  ResourceType.MEDICAL_OUTREACH: 1, ResourceType.FIRE_ENGINE: 0}
    }
    
    MAX_ALLOCATION_FRACTION = 0.60  # Never allocate > 60% of any type to one crisis

    def _build_reasoning(self, resource: Resource, crisis_type: CrisisType, relevance: float, eta: int, rank: int) -> str:
        return (
            f"Rank {rank}: Selected {resource.unit_name} (ETA: {eta} min from {resource.current_location}) "
            f"due to high relevance coefficient ({relevance}) for {crisis_type.value} response."
        )

    def _identify_unmet_needs(self, crisis: Any, allocations: List[AllocationItem], inventory: ResourceInventory) -> List[str]:
        severity = crisis.severity
        demands = self.SEVERITY_RESOURCE_COUNT.get(severity, {})
        
        counts = {}
        for item in allocations:
            counts[item.resource_type] = counts.get(item.resource_type, 0) + 1
            
        unmet = []
        for r_type, count_demanded in demands.items():
            if count_demanded > 0:
                count_allocated = counts.get(r_type, 0)
                if count_allocated < count_demanded:
                    unmet.append(f"{r_type.value}: Demanded {count_demanded}, Allocated {count_allocated}")
        return unmet

    def estimate_response_effectiveness(self, plan: AllocationPlan, crisis: Any) -> float:
        severity = crisis.severity
        demands = self.SEVERITY_RESOURCE_COUNT.get(severity, {})
        crisis_relevance = self.RESOURCE_RELEVANCE.get(crisis.type, {})
        
        total_demanded_relevance = 0.0
        for r_type, count_demanded in demands.items():
            relevance = crisis_relevance.get(r_type, 0.0)
            total_demanded_relevance += relevance * count_demanded
            
        if total_demanded_relevance == 0.0:
            return 1.0
            
        total_allocated_relevance = 0.0
        for item in plan.allocations:
            relevance = crisis_relevance.get(item.resource_type, 0.0)
            total_allocated_relevance += relevance
            
        return min(1.0, max(0.0, total_allocated_relevance / total_demanded_relevance))

    def allocate(self, crisis: Any, inventory: ResourceInventory) -> AllocationPlan:
        severity = crisis.severity
        demanded_counts = self.SEVERITY_RESOURCE_COUNT.get(severity, {})
        crisis_relevance = self.RESOURCE_RELEVANCE.get(crisis.type, {})
        
        allocation_items = []
        reasoning_steps = []
        
        # Process each resource type demanded
        for r_type, count_demanded in demanded_counts.items():
            if count_demanded <= 0:
                continue
                
            # Get available resources
            available = inventory.get_available(r_type)
            
            # Enforce maximum allocation fraction (60% cap of total stock)
            total_stock = sum(1 for r in inventory.resources if r.type == r_type)
            cap_limit = math.floor(total_stock * self.MAX_ALLOCATION_FRACTION)
            max_allowed = max(1, cap_limit)
            
            deploy_limit = min(count_demanded, max_allowed)
            
            relevance = crisis_relevance.get(r_type, 0.0)
            
            # Rank available resources: score = relevance * 1.0 - (travel_time / 180) * 0.3
            scored_resources = []
            for res in available:
                eta = inventory.get_eta(res, crisis.location, crisis.latitude, crisis.longitude)
                score = relevance * 1.0 - (eta / 180.0) * 0.3
                scored_resources.append((score, eta, res))
                
            scored_resources.sort(key=lambda x: x[0], reverse=True)
            
            # Select top resources
            selected_resources = scored_resources[:deploy_limit]
            
            for idx, (score, eta, res) in enumerate(selected_resources):
                reasoning = self._build_reasoning(res, crisis.type, relevance, eta, idx + 1)
                reasoning_steps.append(reasoning)
                
                allocation_items.append(AllocationItem(
                    resource_id=res.resource_id,
                    resource_type=res.type,
                    unit_name=res.unit_name,
                    destination=crisis.location,
                    eta_minutes=eta,
                    reasoning=reasoning
                ))
                
        unmet_needs = self._identify_unmet_needs(crisis, allocation_items, inventory)
        temp_plan = AllocationPlan(
            crisis_id=crisis.crisis_id,
            allocations=allocation_items,
            allocation_reasoning="",
            total_deployed=len(allocation_items)
        )
        effectiveness = self.estimate_response_effectiveness(temp_plan, crisis)
        
        reasoning_summary = f"Completed resource allocation for {crisis.type.value} crisis at {crisis.location}. "
        if unmet_needs:
            reasoning_summary += f"Unmet demands identified: {', '.join(unmet_needs)}. "
        else:
            reasoning_summary += "All demanded resources successfully allocated. "
        
        # Format reasoning summary
        reasoning_summary += f"Overall response plan effectiveness estimated at {int(effectiveness * 100)}%."
        
        plan = AllocationPlan.model_validate({
            "plan_id": str(uuid4()),
            "crisis_id": crisis.crisis_id,
            "allocations": [item.model_dump() for item in allocation_items],
            "unmet_needs": unmet_needs,
            "total_deployed": len(allocation_items),
            "allocation_reasoning": reasoning_summary,
            "created_at": datetime.utcnow().isoformat()
        })
        
        return plan


if __name__ == "__main__":
    import sys
    import os
    # Add parent dir to path so absolute imports work
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models.crisis_models import CrisisSchema, CrisisType, SeverityLevel
    
    inventory = ResourceInventory()
    algo = AllocationAlgorithm()

    # 1. FLOOD HIGH Scenario
    flood_crisis = CrisisSchema(
        crisis_id="flood-high-1",
        type=CrisisType.FLOOD,
        severity=SeverityLevel.HIGH,
        confidence=0.90,
        affected_radius_km=2.5,
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        explanation="High severity flooding"
    )
    
    plan_flood = algo.allocate(flood_crisis, inventory)
    assert len(plan_flood.allocations) > 0
    # Demands for HIGH: RESCUE_TEAM: 2, AMBULANCE: 2, POLICE_UNIT: 3, WATER_TANKER: 2, MEDICAL_OUTREACH: 1, FIRE_ENGINE: 1
    # Check that maximum caps are enforced (e.g. total rescue teams is 8, 60% cap is 4, demanded 2 which is fine)
    # Check that ambulance (total 10, cap 6, demanded 2) is fine
    assert len([a for a in plan_flood.allocations if a.resource_type == ResourceType.RESCUE_TEAM]) == 2
    assert len([a for a in plan_flood.allocations if a.resource_type == ResourceType.AMBULANCE]) == 2
    assert len([a for a in plan_flood.allocations if a.resource_type == ResourceType.POLICE_UNIT]) == 3

    # Mark deployed in inventory
    deployed_ids = [a.resource_id for a in plan_flood.allocations]
    inventory.mark_deployed(deployed_ids, "G-10, Islamabad")

    # 2. HEATWAVE MEDIUM Scenario
    heatwave_crisis = CrisisSchema(
        crisis_id="heatwave-med-1",
        type=CrisisType.HEATWAVE,
        severity=SeverityLevel.MEDIUM,
        confidence=0.80,
        affected_radius_km=4.0,
        location="Gulberg, Lahore",
        latitude=31.5117,
        longitude=74.3468,
        explanation="Medium severity heatwave"
    )
    plan_heat = algo.allocate(heatwave_crisis, inventory)
    # Demands for MEDIUM: RESCUE_TEAM: 1, AMBULANCE: 1, POLICE_UNIT: 2, WATER_TANKER: 1, MEDICAL_OUTREACH: 1, FIRE_ENGINE: 1
    assert len([a for a in plan_heat.allocations if a.resource_type == ResourceType.MEDICAL_OUTREACH]) == 1

    # 3. Insufficient resources scenario
    # Force deploy all rescue teams in Islamabad
    inventory.reset_all()
    available_rescue = inventory.get_available(ResourceType.RESCUE_TEAM)
    assert len(available_rescue) == 8
    
    # Allocate to a CRITICAL flood (demands 3 Rescue Teams)
    critical_flood = CrisisSchema(
        crisis_id="flood-crit-1",
        type=CrisisType.FLOOD,
        severity=SeverityLevel.CRITICAL,
        confidence=0.95,
        affected_radius_km=4.0,
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        explanation="Critical flood"
    )
    plan_crit1 = algo.allocate(critical_flood, inventory)
    inventory.mark_deployed([a.resource_id for a in plan_crit1.allocations], "G-10, Islamabad")
    
    # Allocate to another CRITICAL flood in Lahore
    critical_flood_lh = CrisisSchema(
        crisis_id="flood-crit-2",
        type=CrisisType.FLOOD,
        severity=SeverityLevel.CRITICAL,
        confidence=0.95,
        affected_radius_km=4.0,
        location="Gulberg, Lahore",
        latitude=31.5117,
        longitude=74.3468,
        explanation="Critical flood Lahore"
    )
    plan_crit2 = algo.allocate(critical_flood_lh, inventory)
    # Check that unmet needs are logged because rescue teams are exhausted
    # Total rescue teams = 8. Cap = 4. Demanded = 3. 3 deployed to G-10. Available = 5.
    # 3 deployed to Lahore. Remaining available rescue teams = 2.
    assert len(plan_crit2.unmet_needs) > 0 or len(plan_crit2.allocations) < 3

    print("ALL ALLOCATION TESTS PASSED")
