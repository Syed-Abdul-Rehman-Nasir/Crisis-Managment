from datetime import datetime
from typing import Dict, Any

try:
    from models import AllocationPlan, StakeholderMessages, CrisisSchema
except ImportError:
    from ..models import AllocationPlan, StakeholderMessages, CrisisSchema

class EvaluationMetrics:
    """Computes performance metrics comparing CIRO vs baseline."""
    
    def compute_detection_latency(self, signal_arrival_time: datetime, crisis_detected_time: datetime) -> int:
        """Returns milliseconds between first signal and classification output."""
        delta = crisis_detected_time - signal_arrival_time
        return int(delta.total_seconds() * 1000)
    
    def compute_resource_efficiency(self, deployed_plan: AllocationPlan, optimal_plan: AllocationPlan) -> float:
        """
        Returns ratio: optimal_resources_needed / actual_resources_deployed.
        Clamp to 0.0-1.0.
        """
        actual = len(deployed_plan.allocations)
        optimal = len(optimal_plan.allocations)
        if actual == 0:
            return 0.0
        return min(1.0, max(0.0, optimal / actual))
    
    def compute_false_positive_rate(self, total_alerts: int, false_positives: int) -> float:
        """Standard rate as percentage. Guard against division by zero."""
        if total_alerts == 0:
            return 0.0
        return round((false_positives / total_alerts) * 100.0, 2)
    
    def compute_stakeholder_coverage(self, messages: StakeholderMessages) -> Dict[str, Any]:
        """
        Calculates a coverage score (out of 1.0) based on message fields populated.
        """
        fields = [
            ("public_urdu", messages.public_urdu),
            ("public_english", messages.public_english),
            ("hospital_request", messages.hospital_request),
            ("utility_alert", messages.utility_alert),
            ("transport_rerouting", messages.transport_rerouting),
            ("media_briefing", messages.media_briefing),
        ]
        
        valid_fields = {name: (bool(val and len(val.strip()) > 10)) for name, val in fields}
        total_present = sum(1 for present in valid_fields.values() if present)
        coverage_score = round(total_present / len(fields), 2)
        
        return {
            "total_message_types": len(fields),
            "has_urdu": valid_fields["public_urdu"],
            "has_english": valid_fields["public_english"],
            "has_hospital": valid_fields["hospital_request"],
            "has_utility": valid_fields["utility_alert"],
            "has_transport": valid_fields["transport_rerouting"],
            "has_media": valid_fields["media_briefing"],
            "coverage_score": coverage_score
        }
    
    def generate_full_metrics_report(self, crisis: CrisisSchema,
                                     allocation: AllocationPlan,
                                     messages: StakeholderMessages,
                                     detection_latency_ms: int,
                                     baseline_comparison: Dict[str, Any]) -> Dict[str, Any]:
        coverage = self.compute_stakeholder_coverage(messages)
        
        return {
            "crisis_id": crisis.crisis_id,
            "crisis_type": crisis.type.value,
            "severity": crisis.severity.value,
            "detection_latency_ms": detection_latency_ms,
            "resources_deployed": len(allocation.allocations),
            "unmet_needs_count": len(allocation.unmet_needs),
            "stakeholder_coverage": coverage,
            "baseline_comparison": baseline_comparison,
            "generated_at": datetime.utcnow().isoformat()
        }


if __name__ == "__main__":
    metrics = EvaluationMetrics()

    # Test detection latency
    start = datetime(2026, 5, 20, 12, 0, 0)
    end = datetime(2026, 5, 20, 12, 0, 2, 500000) # 2.5 seconds
    latency = metrics.compute_detection_latency(start, end)
    assert latency == 2500, f"Expected 2500, got {latency}"

    # Test false positive rate
    rate = metrics.compute_false_positive_rate(10, 2)
    assert rate == 20.0, f"Expected 20.0, got {rate}"

    # Test stakeholder coverage
    msg = StakeholderMessages(
        crisis_id="123",
        public_urdu="Urdu script goes here warning residents",
        public_english="English script goes here warning residents",
        hospital_request="Standby trauma ward immediately",
        utility_alert="Clear water lines",
        transport_rerouting="Reroute traffic around main roads",
        media_briefing="Briefing on urban crisis situation"
    )
    cov = metrics.compute_stakeholder_coverage(msg)
    assert cov["coverage_score"] == 1.0
    assert cov["has_urdu"] is True

    print("ALL METRICS TESTS PASSED")
