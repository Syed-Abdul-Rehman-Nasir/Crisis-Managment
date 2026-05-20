import math
from typing import List, Dict, Any

try:
    from models import SignalSource, RawSignal, ScoredSignal
except ImportError:
    from ..models import SignalSource, RawSignal, ScoredSignal

class SignalCredibility:
    """
    Computes a weighted credibility score for each incoming signal.
    Used by the SignalFusionAgent before classification.
    """
    
    WEIGHTS = {
        "source": 0.35,
        "recency": 0.25,
        "frequency": 0.25,
        "geo": 0.15
    }
    
    SOURCE_BASE_SCORES = {
        SignalSource.WEATHER_API: 0.95,
        SignalSource.GOOGLE_MAPS: 0.90,
        SignalSource.HISTORICAL_DATA: 0.85,
        SignalSource.EMERGENCY_CALL: 0.88,
        SignalSource.SOCIAL_MEDIA: 0.60
    }

    def _compute_source_score(self, source_type: SignalSource, recency_minutes: int = 0) -> float:
        base = self.SOURCE_BASE_SCORES.get(source_type, 0.50)
        if source_type == SignalSource.SOCIAL_MEDIA and recency_minutes > 30:
            return base * 0.85
        return base

    def _compute_recency_score(self, recency_minutes: int) -> float:
        # Exponential decay: score = e^(-recency_minutes / 60)
        return math.exp(-recency_minutes / 60.0)

    def _compute_frequency_score(self, mention_frequency: int) -> float:
        # Logarithmic scaling zero-anchored at frequency=1 and reaching 1.0 at frequency=50
        # Formula: score = min(1.0, max(0.0, (log(1 + f) - log(2)) / (log(51) - log(2))))
        return min(1.0, max(0.0,
            (math.log(1 + mention_frequency) - math.log(2)) /
            (math.log(51) - math.log(2))
        ))

    def _compute_geo_score(self, geo_precision: float) -> float:
        # Direct passthrough with a floor of 0.1
        return max(0.1, geo_precision)

    def score_signal(self, signal: RawSignal) -> ScoredSignal:
        s_score = self._compute_source_score(signal.source_type, signal.recency_minutes)
        r_score = self._compute_recency_score(signal.recency_minutes)
        f_score = self._compute_frequency_score(signal.mention_frequency)
        g_score = self._compute_geo_score(signal.geo_precision)

        composite = (
            s_score * self.WEIGHTS["source"] +
            r_score * self.WEIGHTS["recency"] +
            f_score * self.WEIGHTS["frequency"] +
            g_score * self.WEIGHTS["geo"]
        )
        
        explanation = {
            "source_score": round(s_score, 4),
            "source_weight": self.WEIGHTS["source"],
            "recency_score": round(r_score, 4),
            "recency_weight": self.WEIGHTS["recency"],
            "frequency_score": round(f_score, 4),
            "frequency_weight": self.WEIGHTS["frequency"],
            "geo_score": round(g_score, 4),
            "geo_weight": self.WEIGHTS["geo"],
            "composite_score": round(composite, 4),
            "dominant_factor": max(
                [("source", s_score * self.WEIGHTS["source"]),
                 ("recency", r_score * self.WEIGHTS["recency"]),
                 ("frequency", f_score * self.WEIGHTS["frequency"]),
                 ("geo", g_score * self.WEIGHTS["geo"])],
                key=lambda x: x[1]
            )[0]
        }

        # Create ScoredSignal
        return ScoredSignal(
            signal_id=signal.signal_id,
            source_type=signal.source_type,
            content=signal.content,
            location=signal.location,
            latitude=signal.latitude,
            longitude=signal.longitude,
            timestamp=signal.timestamp,
            recency_minutes=signal.recency_minutes,
            mention_frequency=signal.mention_frequency,
            geo_precision=signal.geo_precision,
            raw_metadata=signal.raw_metadata,
            credibility_score=round(composite, 4),
            credibility_explanation=explanation
        )

    def score_batch(self, signals: List[RawSignal]) -> List[ScoredSignal]:
        scored = [self.score_signal(s) for s in signals]
        # Sort by credibility_score descending
        scored.sort(key=lambda x: x.credibility_score, reverse=True)
        return scored

    def get_top_signals(self, signals: List[RawSignal], top_n: int = 5) -> List[ScoredSignal]:
        return self.score_batch(signals)[:top_n]


if __name__ == "__main__":
    # Test suite implementation
    import sys
    import os
    # Add parent dir to path so absolute imports work
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models.signal_models import RawSignal, SignalSource

    engine = SignalCredibility()

    # 1. High-credibility weather API signal
    weather_sig = RawSignal(
        source_type=SignalSource.WEATHER_API,
        content="Heavy rain in G-10",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=2,
        mention_frequency=10,
        geo_precision=0.9
    )
    scored_weather = engine.score_signal(weather_sig)
    assert scored_weather.credibility_score > 0.80, f"Weather API score too low: {scored_weather.credibility_score}"

    # 2. Low-credibility old social media post (recency=120 min)
    old_social_sig = RawSignal(
        source_type=SignalSource.SOCIAL_MEDIA,
        content="flood in Islamabad",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=120,
        mention_frequency=2,
        geo_precision=0.5
    )
    scored_old = engine.score_signal(old_social_sig)
    assert scored_old.credibility_score < 0.45, f"Old social media score too high: {scored_old.credibility_score}"

    # 3. Medium-credibility emergency call with imprecise location
    call_sig = RawSignal(
        source_type=SignalSource.EMERGENCY_CALL,
        content="Water on roads",
        location="Islamabad",
        latitude=33.6844,
        longitude=73.0479,
        recency_minutes=15,
        mention_frequency=1,
        geo_precision=0.2
    )
    scored_call = engine.score_signal(call_sig)
    assert 0.45 < scored_call.credibility_score < 0.75, f"Emergency call score out of bounds: {scored_call.credibility_score}"

    # 4. frequency=1 -> frequency_score == 0.0 (EXACT)
    f_score_1 = engine._compute_frequency_score(1)
    assert f_score_1 == 0.0, f"Expected 0.0, got {f_score_1}"

    # 5. frequency=50 -> frequency_score == 1.0 (EXACT)
    f_score_50 = engine._compute_frequency_score(50)
    assert f_score_50 == 1.0, f"Expected 1.0, got {f_score_50}"

    # 6. Verification that weights sum to 1.0 exactly
    assert sum(engine.WEIGHTS.values()) == 1.0

    # 7. Social media recency penalty test
    social_fresh = RawSignal(
        source_type=SignalSource.SOCIAL_MEDIA,
        content="Water on roads",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=5,
        mention_frequency=5,
        geo_precision=0.8
    )
    social_stale = RawSignal(
        source_type=SignalSource.SOCIAL_MEDIA,
        content="Water on roads",
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        recency_minutes=35,
        mention_frequency=5,
        geo_precision=0.8
    )
    source_fresh = engine._compute_source_score(social_fresh.source_type, social_fresh.recency_minutes)
    source_stale = engine._compute_source_score(social_stale.source_type, social_stale.recency_minutes)
    assert source_stale < source_fresh, "Social media recency penalty not applied"

    # 8. Batch scoring sorting check
    batch = engine.score_batch([old_social_sig, weather_sig, call_sig])
    assert batch[0].signal_id == weather_sig.signal_id
    assert batch[2].signal_id == old_social_sig.signal_id

    print("ALL CREDIBILITY TESTS PASSED")
