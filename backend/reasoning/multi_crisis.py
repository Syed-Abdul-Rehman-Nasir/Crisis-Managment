from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Any

try:
    from models import CrisisSchema, MultiCrisisAllocationPlan, AllocationPlan, get_severity_score, ResourceType
    from reasoning.resource_model import ResourceInventory
    from reasoning.allocation import AllocationAlgorithm
except ImportError:
    from ..models import CrisisSchema, MultiCrisisAllocationPlan, AllocationPlan, get_severity_score, ResourceType
    from .resource_model import ResourceInventory
    from .allocation import AllocationAlgorithm

class MultiCrisisCoordinator:
    """
    Prioritizes multiple concurrent crises based on severity, confidence, and
    population impact, resolving resource contention conflicts.
    """

    POPULATION_ESTIMATES = {
        "G-10": 85000, "G-11": 90000, "I-8": 75000, "F-6": 45000,
        "F-7": 55000, "F-8": 60000, "E-7": 40000, "Rawal Town": 120000,
        "Gulberg": 180000, "Model Town": 95000, "DHA Phase 4": 110000,
        "Johar Town": 130000, "Cantt": 85000
    }

    def __init__(self):
        import os
        import json
        self.population_estimates = self.POPULATION_ESTIMATES.copy()
        
        # Try loading from the data folder relative to the script location
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_dir, "data", "population_estimates.json")
        
        try:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Ensure keys are strings and values are ints
                        self.population_estimates.update({str(k): int(v) for k, v in data.items()})
        except Exception:
            # Silently fall back to default dict
            pass

    def _compute_priority_score(self, crisis: CrisisSchema) -> float:
        severity_score = get_severity_score(crisis.severity)
        
        # Parse sector or zone name from location string
        # e.g., "G-10, Islamabad" -> "G-10"
        loc_part = crisis.location.split(",")[0].strip()
        population = self.population_estimates.get(loc_part, 50000)
        population_score = min(1.0, population / 100000.0)
        
        # Priority formula: severity * 2 + confidence * 1 + population_score
        return severity_score * 2.0 + crisis.confidence * 1.0 + population_score

    def _log_conflict(self, resource_type: ResourceType, assigned_to: str, denied_to: str, reason: str) -> str:
        return (
            f"Resource contention resolved: {resource_type.value.upper()} deployed to {assigned_to} "
            f"and denied to {denied_to}. Reason: {reason}."
        )

    def generate_trade_off_summary(self, plan: MultiCrisisAllocationPlan) -> str:
        if not plan.crisis_plans:
            return "No active allocations to coordinate."
            
        summary = f"Coordinated response for {len(plan.crisis_plans)} crises. Priority order: "
        summary += " -> ".join([plan.crisis_plans[cid].crisis_id for cid in plan.priority_order])
        summary += ". "
        
        if plan.conflict_resolution_log:
            summary += f"Resolved {len(plan.conflict_resolution_log)} resource contentions. "
            summary += " ".join(plan.conflict_resolution_log)
        else:
            summary += "No resource contention encountered during routing."
            
        return summary

    def coordinate(self, crises: List[CrisisSchema], inventory: ResourceInventory) -> MultiCrisisAllocationPlan:
        # 1. Compute priority score for each active crisis
        scored_crises = []
        for c in crises:
            if c.is_active:
                score = self._compute_priority_score(c)
                scored_crises.append((score, c))
                
        # 2. Sort by priority score descending
        scored_crises.sort(key=lambda x: x[0], reverse=True)
        
        plan_id = str(uuid4())
        crisis_plans = {}
        conflict_resolution_log = []
        priority_order = []
        
        algo = AllocationAlgorithm()
        allocated_by_type = {}  # Keep track of what types were allocated and to whom
        
        # 3. Allocate to highest priority first
        for score, crisis in scored_crises:
            priority_order.append(crisis.crisis_id)
            
            # Save pre-allocation available stock to check for contentions later
            pre_available = {}
            for r_type in ResourceType:
                pre_available[r_type] = len(inventory.get_available(r_type))
                
            # Perform allocation
            plan = algo.allocate(crisis, inventory)
            
            # Mark deployed in inventory
            deployed_ids = [item.resource_id for item in plan.allocations]
            inventory.mark_deployed(deployed_ids, crisis.location)
            
            crisis_plans[crisis.crisis_id] = plan
            
            # 4. Check for contentions / unmet needs
            for unmet in plan.unmet_needs:
                # unmet format: "rescue_team: Demanded 3, Allocated 1"
                parts = unmet.split(":")
                if len(parts) >= 2:
                    r_type_str = parts[0].strip()
                    try:
                        r_type = ResourceType(r_type_str)
                    except ValueError:
                        continue
                        
                    # If this type had available stock earlier but was taken by a higher priority crisis
                    taken_by = []
                    for prev_cid, prev_plan in crisis_plans.items():
                        if prev_cid == crisis.crisis_id:
                            continue
                        count_taken = len([a for a in prev_plan.allocations if a.resource_type == r_type])
                        if count_taken > 0:
                            taken_by.append((prev_cid, count_taken))
                            
                    if taken_by:
                        assigned_names = ", ".join([f"{count} units to {cid}" for cid, count in taken_by])
                        reason = f"higher priority crisis requirements (allocated {assigned_names})"
                        conflict_log = self._log_conflict(
                            resource_type=r_type,
                            assigned_to=assigned_names,
                            denied_to=crisis.crisis_id,
                            reason=reason
                        )
                        conflict_resolution_log.append(conflict_log)
                        
        # Construct and return coordinate plan
        m_plan = MultiCrisisAllocationPlan(
            plan_id=plan_id,
            crisis_plans=crisis_plans,
            conflict_resolution_log=conflict_resolution_log,
            priority_order=priority_order,
            created_at=datetime.utcnow()
        )
        
        return m_plan
