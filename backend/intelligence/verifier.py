from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from uuid import uuid4

try:
    from models import CrisisType, SeverityLevel, get_severity_score, CrisisSchema, ScoredSignal, SignalSource, FalsePositiveResult
except ImportError:
    from ..models import CrisisType, SeverityLevel, get_severity_score, CrisisSchema, ScoredSignal, SignalSource, FalsePositiveResult

class FalsePositiveVerifier:
    """
    Detects when a contradicting signal invalidates an existing crisis classification.
    """
    
    RETRACTION_THRESHOLD = 0.60
    
    CORRECTION_KEYWORDS = {
        "water main burst": {
            "replaces": CrisisType.FLOOD,
            "corrects_to": CrisisType.INFRASTRUCTURE,
            "contradiction_weight": 0.45
        },
        "pipe burst": {
            "replaces": CrisisType.FLOOD,
            "corrects_to": CrisisType.INFRASTRUCTURE,
            "contradiction_weight": 0.40
        },
        "sprinkler": {
            "replaces": CrisisType.FLOOD,
            "corrects_to": None,
            "contradiction_weight": 0.35
        },
        "controlled burn": {
            "replaces": CrisisType.FIRE,
            "corrects_to": None,
            "contradiction_weight": 0.30
        },
        "training exercise": {
            "replaces": CrisisType.ACCIDENT,
            "corrects_to": None,
            "contradiction_weight": 0.40
        },
        "false alarm": {
            "replaces": None,
            "contradiction_weight": 0.30
        },
        "road repair": {
            "replaces": CrisisType.ACCIDENT,
            "corrects_to": CrisisType.INFRASTRUCTURE,
            "contradiction_weight": 0.35
        }
    }

    AUTHORITATIVE_SOURCES = [SignalSource.EMERGENCY_CALL, SignalSource.WEATHER_API]

    def _find_best_correction_keyword(self, content: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        content_lower = content.lower()
        best_kw = None
        best_data = None
        for kw, data in self.CORRECTION_KEYWORDS.items():
            if kw in content_lower:
                if not best_data or data["contradiction_weight"] > best_data["contradiction_weight"]:
                    best_kw = kw
                    best_data = data
        if best_kw:
            return best_kw, best_data
        return None

    def _build_log_entry(self, original: CrisisSchema, result: FalsePositiveResult, new_signal: ScoredSignal) -> str:
        status_str = "RETRACTED" if result.retract else "MAINTAINED"
        corr_str = f" Corrected to {result.corrected_type.value}." if result.corrected_type else ""
        return (
            f"Verification audit for crisis {original.crisis_id} ({original.type.value} at {original.location}): "
            f"{status_str} by signal {new_signal.signal_id} (contradiction score: {round(result.contradiction_score, 2)}).{corr_str}"
        )

    def verify(self, new_signal: ScoredSignal, active_crisis: CrisisSchema) -> FalsePositiveResult:
        verification_log = [f"Starting verifier monitoring for signal {new_signal.signal_id} vs crisis {active_crisis.crisis_id} ({active_crisis.type.value})."]
        
        match = self._find_best_correction_keyword(new_signal.content)
        if not match:
            verification_log.append("No contradiction keyword detected in signal content. Crisis validation maintained.")
            return FalsePositiveResult(
                original_crisis_id=active_crisis.crisis_id,
                contradiction_score=0.0,
                retract=False,
                correction="No contradiction keyword found.",
                log_entry=f"Verified {active_crisis.crisis_id}: no contradiction found.",
                verification_log=verification_log
            )

        kw, data = match
        replaces_type = data.get("replaces")
        
        # Check if the keyword actually invalidates this crisis type
        if replaces_type and replaces_type != active_crisis.type:
            verification_log.append(f"Contradiction keyword '{kw}' replaces '{replaces_type.value}', which does not match active crisis type '{active_crisis.type.value}'. Maintain.")
            return FalsePositiveResult(
                original_crisis_id=active_crisis.crisis_id,
                contradiction_score=0.0,
                retract=False,
                correction=f"Contradiction mismatch: keyword {kw} does not target {active_crisis.type.value}.",
                log_entry=f"Verified {active_crisis.crisis_id}: no contradiction found.",
                verification_log=verification_log
            )

        verification_log.append(f"Contradiction keyword detected: '{kw}' with base contradiction weight {data['contradiction_weight']}.")
        
        base = data["contradiction_weight"]
        authority_boost = 0.15 if new_signal.source_type in self.AUTHORITATIVE_SOURCES else 0.0
        recency_bonus = 0.10 if new_signal.recency_minutes < 5 else 0.0
        credibility_factor = new_signal.credibility_score * 0.20
        
        contradiction_score = min(1.0, base + authority_boost + recency_bonus + credibility_factor)
        retract = contradiction_score > self.RETRACTION_THRESHOLD
        
        verification_log.append(f"Score components - base: {base}, authority boost: {authority_boost}, recency bonus: {recency_bonus}, credibility factor: {round(credibility_factor, 2)}.")
        verification_log.append(f"Final contradiction score: {round(contradiction_score, 2)} (Threshold: {self.RETRACTION_THRESHOLD}).")
        verification_log.append(f"Action: {'RETRACT CRISIS' if retract else 'MAINTAIN CRISIS'}.")

        corrected_type = data.get("corrects_to")
        correction = f"Retracted flood and corrected to {corrected_type.value}" if corrected_type else "Retracted alert (false alarm)"

        res = FalsePositiveResult(
            original_crisis_id=active_crisis.crisis_id,
            contradiction_score=round(contradiction_score, 4),
            retract=retract,
            correction=correction,
            corrected_type=corrected_type,
            log_entry="",
            verification_log=verification_log
        )
        
        res.log_entry = self._build_log_entry(active_crisis, res, new_signal)
        return res

    def retract_and_update(self, crisis: CrisisSchema, result: FalsePositiveResult) -> CrisisSchema:
        if result.retract:
            crisis.retracted = True
            crisis.is_active = False
            crisis.retraction_reason = result.correction
            crisis.reasoning_log.append(f"Alert retracted: {result.correction}. Timestamp: {result.correction_timestamp.isoformat()}. Verifier log: {result.log_entry}")
            
            # If corrected to another type
            if result.corrected_type:
                crisis.reasoning_log.append(f"Updated crisis type classification to {result.corrected_type.value}.")
        return crisis

    def batch_verify(self, new_signals: List[ScoredSignal], active_crises: List[CrisisSchema]) -> List[FalsePositiveResult]:
        results = []
        for signal in new_signals:
            for crisis in active_crises:
                if crisis.is_active:
                    res = self.verify(signal, crisis)
                    if res.contradiction_score > 0:
                        results.append(res)
        return results


if __name__ == "__main__":
    import sys
    import os
    # Add parent dir to path so absolute imports work
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models.signal_models import RawSignal, SignalSource
    from models.crisis_models import CrisisSchema, CrisisType, SeverityLevel
    from intelligence.credibility import SignalCredibility

    cred_engine = SignalCredibility()
    verifier = FalsePositiveVerifier()

    # Setup active flood crisis
    active_flood = CrisisSchema(
        crisis_id="flood-123",
        type=CrisisType.FLOOD,
        severity=SeverityLevel.HIGH,
        confidence=0.85,
        affected_radius_km=2.4,
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        explanation="Flood detected",
        contributing_signals=["sig-1"]
    )

    # 1. Authoritative Emergency Call reporting a water main burst
    raw_signal_auth = RawSignal(
        source_type=SignalSource.EMERGENCY_CALL,
        content="This is CDA water department, we have a water main burst on 7th avenue G-10, not a natural flood.",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=2,
        mention_frequency=1,
        geo_precision=0.9
    )
    scored_auth = cred_engine.score_signal(raw_signal_auth)
    res_auth = verifier.verify(scored_auth, active_flood)
    assert res_auth.retract is True
    assert res_auth.contradiction_score > 0.60
    assert res_auth.corrected_type == CrisisType.INFRASTRUCTURE

    # 2. General weather alert (no contradiction keyword)
    raw_signal_general = RawSignal(
        source_type=SignalSource.WEATHER_API,
        content="Heavy rain expected to continue for 2 more hours.",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=4,
        mention_frequency=1,
        geo_precision=0.95
    )
    scored_general = cred_engine.score_signal(raw_signal_general)
    res_general = verifier.verify(scored_general, active_flood)
    assert res_general.retract is False
    assert res_general.contradiction_score == 0.0

    # 3. Authority Boost test (Emergency call vs Social media)
    raw_social = RawSignal(
        source_type=SignalSource.SOCIAL_MEDIA,
        content="Maybe it is just a water main burst in G-10.",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=2,
        mention_frequency=1,
        geo_precision=0.8
    )
    scored_social = cred_engine.score_signal(raw_social)
    res_social = verifier.verify(scored_social, active_flood)
    
    # Auth signal contradiction score should be higher because of authority boost (+0.15)
    assert res_auth.contradiction_score > res_social.contradiction_score

    # 4. Recency Bonus test (recency_minutes=2 vs recency_minutes=30)
    raw_stale = RawSignal(
        source_type=SignalSource.EMERGENCY_CALL,
        content="This is CDA water department, we have a water main burst on 7th avenue G-10, not a natural flood.",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=30,
        mention_frequency=1,
        geo_precision=0.9
    )
    scored_stale = cred_engine.score_signal(raw_stale)
    res_stale = verifier.verify(scored_stale, active_flood)
    
    # Fresh signal (recency < 5) should score higher (+0.10 recency bonus)
    assert res_auth.contradiction_score > res_stale.contradiction_score

    # 5. Batch Verify
    fp_results = verifier.batch_verify([scored_auth, scored_general], [active_flood])
    assert len(fp_results) == 1
    assert fp_results[0].retract is True

    print("ALL VERIFIER TESTS PASSED")
