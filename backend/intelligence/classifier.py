from typing import List, Dict, Any, Tuple
from datetime import datetime
from uuid import uuid4

try:
    from models import CrisisType, SeverityLevel, get_severity_score, CrisisSchema, ScoredSignal, SignalSource
except ImportError:
    from ..models import CrisisType, SeverityLevel, get_severity_score, CrisisSchema, ScoredSignal, SignalSource

class CrisisClassifier:
    """
    Multi-signal crisis classification using weighted voting and
    threshold-based severity assignment. Fully deterministic and explainable.
    """

    CRISIS_KEYWORDS = {
        CrisisType.FLOOD: {
            "urdu_roman": ["pani bhar gaya", "sailaab", "baarish", "tayfaan",
                           "nali bhari", "khet doob gaye"],
            "english": ["flood", "flooding", "waterlogged", "submerged",
                        "overflow", "inundation", "standing water", "drainage blocked"]
        },
        CrisisType.HEATWAVE: {
            "urdu_roman": ["garmi", "luu", "heat stroke", "paani khatam", "tapish"],
            "english": ["heatwave", "heat wave", "extreme heat", "temperature spike",
                        "heat stroke", "heat advisory", "temperature"]
        },
        CrisisType.ACCIDENT: {
            "urdu_roman": ["haadsa", "takkar", "car accident", "road block", "aag lag gayi"],
            "english": ["accident", "collision", "crash", "road block",
                        "pile-up", "overturned", "emergency"]
        },
        CrisisType.INFRASTRUCTURE: {
            "urdu_roman": ["bijli gayi", "paani band", "main burst",
                           "pipe phoot", "transformer"],
            "english": ["power outage", "water main", "pipe burst",
                        "infrastructure failure", "utility failure", "transformer fire"]
        },
        CrisisType.FIRE: {
            "urdu_roman": ["aag", "dhuaan", "jal raha"],
            "english": ["fire", "smoke", "blaze", "burning", "firefighter"]
        }
    }

    SEVERITY_THRESHOLDS = {
        "critical": (0.85, 4, 0.7),
        "high":     (0.70, 3, 0.5),
        "medium":   (0.55, 2, 0.3),
        "low":      (0.0,  1, 0.0)
    }

    SOURCE_SEVERITY_BOOST = {
        SignalSource.WEATHER_API:     {"FLOOD": 1, "HEATWAVE": 1},
        SignalSource.EMERGENCY_CALL:  {"FLOOD": 1, "ACCIDENT": 1, "FIRE": 1},
        SignalSource.GOOGLE_MAPS:     {"ACCIDENT": 1, "FLOOD": 1}
    }

    def _matches_type(self, signal: ScoredSignal, crisis_type: CrisisType) -> bool:
        content_lower = signal.content.lower()
        import re
        keywords = self.CRISIS_KEYWORDS.get(crisis_type, {})
        for kw in keywords.get("english", []) + keywords.get("urdu_roman", []):
            if len(kw) <= 4:
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, content_lower):
                    return True
            else:
                if kw in content_lower:
                    return True
        return False

    def _score_signals_for_type(self, signals: List[ScoredSignal], crisis_type: CrisisType) -> float:
        return sum(s.credibility_score for s in signals if self._matches_type(s, crisis_type))

    def _compute_severity(self, signals: List[ScoredSignal], crisis_type: CrisisType) -> SeverityLevel:
        matching = [s for s in signals if self._matches_type(s, crisis_type)]
        if not matching:
            return SeverityLevel.LOW
        
        avg_cred = sum(s.credibility_score for s in matching) / len(matching)
        
        # Determine base severity from thresholds
        if avg_cred >= 0.85:
            base = SeverityLevel.CRITICAL
        elif avg_cred >= 0.70:
            base = SeverityLevel.HIGH
        elif avg_cred >= 0.55:
            base = SeverityLevel.MEDIUM
        else:
            base = SeverityLevel.LOW
        
        # Check source severity boost
        boost = 0
        for s in matching:
            boost_dict = self.SOURCE_SEVERITY_BOOST.get(s.source_type, {})
            boost_val = boost_dict.get(crisis_type.name.upper(), 0)
            boost = max(boost, boost_val)
            
        if boost > 0:
            if base == SeverityLevel.LOW:
                base = SeverityLevel.MEDIUM
            elif base == SeverityLevel.MEDIUM:
                base = SeverityLevel.HIGH
            elif base == SeverityLevel.HIGH or base == SeverityLevel.CRITICAL:
                base = SeverityLevel.CRITICAL
                
        return base

    def _estimate_radius(self, crisis_type: CrisisType, severity: SeverityLevel) -> float:
        radii = {
            CrisisType.FLOOD:          {SeverityLevel.LOW: 0.5, SeverityLevel.MEDIUM: 1.2, SeverityLevel.HIGH: 2.5, SeverityLevel.CRITICAL: 4.0},
            CrisisType.HEATWAVE:       {SeverityLevel.LOW: 2.0, SeverityLevel.MEDIUM: 4.0, SeverityLevel.HIGH: 8.0, SeverityLevel.CRITICAL: 15.0},
            CrisisType.ACCIDENT:       {SeverityLevel.LOW: 0.1, SeverityLevel.MEDIUM: 0.3, SeverityLevel.HIGH: 0.5, SeverityLevel.CRITICAL: 1.0},
            CrisisType.INFRASTRUCTURE: {SeverityLevel.LOW: 0.2, SeverityLevel.MEDIUM: 0.8, SeverityLevel.HIGH: 1.5, SeverityLevel.CRITICAL: 3.0},
            CrisisType.FIRE:           {SeverityLevel.LOW: 0.1, SeverityLevel.MEDIUM: 0.5, SeverityLevel.HIGH: 1.0, SeverityLevel.CRITICAL: 2.0}
        }
        return radii.get(crisis_type, {}).get(severity, 1.0)

    def _build_explanation(self, signals: List[ScoredSignal], winner: CrisisType, confidence: float, severity: SeverityLevel) -> str:
        matching = [s for s in signals if self._matches_type(s, winner)]
        counts = {}
        for s in matching:
            counts[s.source_type.value] = counts.get(s.source_type.value, 0) + 1
        
        sources_str = ", ".join([f"{count} from {src}" for src, count in counts.items()])
        boost_triggered = any(s.source_type in self.SOURCE_SEVERITY_BOOST and winner.name.upper() in self.SOURCE_SEVERITY_BOOST[s.source_type] for s in matching)
        
        boost_str = " (including authority severity boost)" if boost_triggered else ""
        return (
            f"Detected {winner.value} crisis at this location with {severity.value} severity{boost_str}. "
            f"Classification confidence is {int(confidence * 100)}% based on {len(matching)} corroborating signals. "
            f"Signal breakdown: {sources_str or 'none'}. "
            f"Environmental impact radius estimated at {self._estimate_radius(winner, severity)} km."
        )

    def classify(self, signals: List[ScoredSignal], location: str = None) -> CrisisSchema:
        reasoning_log = ["Initializing multi-signal classification..."]
        
        types_to_check = [
            CrisisType.FLOOD,
            CrisisType.HEATWAVE,
            CrisisType.ACCIDENT,
            CrisisType.INFRASTRUCTURE,
            CrisisType.FIRE
        ]
        
        votes = {}
        total_score = 0.0
        for t in types_to_check:
            score = self._score_signals_for_type(signals, t)
            votes[t] = score
            total_score += score
            if score > 0:
                reasoning_log.append(f"Crisis type {t.value} accumulated vote score of {round(score, 2)}.")

        # Default if no votes accumulate
        if total_score == 0:
            return CrisisSchema(
                type=CrisisType.UNKNOWN,
                severity=SeverityLevel.LOW,
                confidence=0.0,
                affected_radius_km=0.0,
                location=location or "Unknown Location",
                latitude=33.6844,
                longitude=73.0479,
                explanation="No signals matched known crisis patterns.",
                reasoning_log=["Classification completed with UNKNOWN classification due to zero keyword matches."]
            )

        # Select winner. If tie, prioritize higher risk in order
        priority_order = [
            CrisisType.FLOOD,
            CrisisType.FIRE,
            CrisisType.HEATWAVE,
            CrisisType.ACCIDENT,
            CrisisType.INFRASTRUCTURE
        ]
        
        winner = max(
            types_to_check,
            key=lambda t: (votes.get(t, 0), priority_order.index(t) if t in priority_order else 99)
        )
        
        winning_score = votes[winner]
        confidence = winning_score / total_score
        
        # Enforce default location if not provided
        matched_sigs = [s for s in signals if self._matches_type(s, winner)]
        loc = location or (matched_sigs[0].location if matched_sigs else "Islamabad, Pakistan")
        lat = matched_sigs[0].latitude if matched_sigs else 33.6844
        lng = matched_sigs[0].longitude if matched_sigs else 73.0479
        
        severity = self._compute_severity(signals, winner)
        radius = self._estimate_radius(winner, severity)
        explanation = self._build_explanation(signals, winner, confidence, severity)
        
        reasoning_log.append(f"Winner: {winner.value} with confidence {round(confidence, 2)}.")
        reasoning_log.append(f"Assigned severity: {severity.value} (based on average credibility and authority boosts).")
        reasoning_log.append("Classification output successfully generated.")

        return CrisisSchema(
            crisis_id=str(uuid4()),
            type=winner,
            severity=severity,
            confidence=round(confidence, 4),
            affected_radius_km=radius,
            location=loc,
            latitude=lat,
            longitude=lng,
            detected_at=datetime.utcnow(),
            explanation=explanation,
            contributing_signals=[s.signal_id for s in matched_sigs],
            reasoning_log=reasoning_log
        )


if __name__ == "__main__":
    import sys
    import os
    # Add parent dir to path so absolute imports work
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models.signal_models import RawSignal, SignalSource
    from intelligence.credibility import SignalCredibility

    cred_engine = SignalCredibility()
    classifier = CrisisClassifier()

    # Test Case 1: G-10 Flood (5 signals)
    raw_signals = [
        RawSignal(source_type=SignalSource.SOCIAL_MEDIA, content="G-10 street is flooded, water rising!", location="G-10, Islamabad", latitude=33.6938, longitude=73.0652, recency_minutes=5, mention_frequency=12, geo_precision=0.8),
        RawSignal(source_type=SignalSource.WEATHER_API, content="Heavy rainfall 80mm in Islamabad", location="G-10, Islamabad", latitude=33.6938, longitude=73.0652, recency_minutes=1, mention_frequency=1, geo_precision=0.95),
        RawSignal(source_type=SignalSource.GOOGLE_MAPS, content="Road closure and severe waterlogging on G-10 main road", location="G-10, Islamabad", latitude=33.6938, longitude=73.0652, recency_minutes=2, mention_frequency=3, geo_precision=0.9),
        RawSignal(source_type=SignalSource.EMERGENCY_CALL, content="Pani gali me aagaya hai, cars sub-merged", location="G-10, Islamabad", latitude=33.6938, longitude=73.0652, recency_minutes=10, mention_frequency=1, geo_precision=0.85),
        RawSignal(source_type=SignalSource.SOCIAL_MEDIA, content="Water is blocking G-10 markaz access", location="G-10, Islamabad", latitude=33.6938, longitude=73.0652, recency_minutes=15, mention_frequency=5, geo_precision=0.7)
    ]
    scored = cred_engine.score_batch(raw_signals)
    crisis = classifier.classify(scored)
    assert crisis.type == CrisisType.FLOOD
    assert crisis.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
    assert crisis.confidence > 0.8

    # Test Case 2: Gulberg Heatwave (3 signals)
    heat_signals = [
        RawSignal(source_type=SignalSource.SOCIAL_MEDIA, content="Extremely hot in Gulberg today, luu chal rahi hai", location="Gulberg, Lahore", latitude=33.6007, longitude=73.0679, recency_minutes=10, mention_frequency=8, geo_precision=0.8),
        RawSignal(source_type=SignalSource.WEATHER_API, content="Temperature reaches 44C in Lahore", location="Gulberg, Lahore", latitude=33.6007, longitude=73.0679, recency_minutes=5, mention_frequency=1, geo_precision=0.95),
        RawSignal(source_type=SignalSource.EMERGENCY_CALL, content="Heat stroke victim in Gulberg Markaz", location="Gulberg, Lahore", latitude=33.6007, longitude=73.0679, recency_minutes=8, mention_frequency=1, geo_precision=0.9)
    ]
    scored_heat = cred_engine.score_batch(heat_signals)
    crisis_heat = classifier.classify(scored_heat)
    assert crisis_heat.type == CrisisType.HEATWAVE
    assert crisis_heat.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]

    # Test Case 3: Ambiguous conflicting signals
    ambig_signals = [
        RawSignal(source_type=SignalSource.SOCIAL_MEDIA, content="G-10 is flooded!", location="G-10, Islamabad", latitude=33.6938, longitude=73.0652, recency_minutes=5, mention_frequency=2, geo_precision=0.8),
        RawSignal(source_type=SignalSource.SOCIAL_MEDIA, content="G-10 garmi bohot hai, tapish extreme", location="G-10, Islamabad", latitude=33.6938, longitude=73.0652, recency_minutes=5, mention_frequency=2, geo_precision=0.8)
    ]
    scored_ambig = cred_engine.score_batch(ambig_signals)
    crisis_ambig = classifier.classify(scored_ambig)
    assert crisis_ambig.type in [CrisisType.FLOOD, CrisisType.HEATWAVE]
    assert crisis_ambig.type != CrisisType.UNKNOWN

    print("ALL CLASSIFIER TESTS PASSED")
