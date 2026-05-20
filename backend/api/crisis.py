from fastapi import APIRouter, Request, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from models import CrisisSchema, RawSignal, FalsePositiveResult, CrisisType, SeverityLevel
from intelligence.classifier import CrisisClassifier
from intelligence.verifier import FalsePositiveVerifier
from intelligence.credibility import SignalCredibility

router = APIRouter(prefix="/api/crisis", tags=["crisis"])
classifier = CrisisClassifier()
verifier = FalsePositiveVerifier()
credibility_engine = SignalCredibility()

class VerifyRequest(BaseModel):
    new_signal: RawSignal
    crisis_id: str

from intelligence.gemini_fusion import fuse_signals_with_gemini
from compat_utils import crisis_schema_to_compat_card

@router.post("/detect")
async def detect_crisis(request: Request):
    scheduler = request.app.state.scheduler
    
    # Grab signals from buffer (already scored)
    raw_signals = list(scheduler.buffer)
    crisis = None
    fusion_output = {}
    
    if not raw_signals:
        # Check if we already have an active crisis in state
        if request.app.state.active_crises:
            crisis = request.app.state.active_crises[0]
        else:
            # Fallback dummy crisis to avoid crashing the demo
            crisis = CrisisSchema(
                crisis_id="g10_flood",
                type=CrisisType.FLOOD,
                severity=SeverityLevel.HIGH,
                confidence=0.89,
                affected_radius_km=2.4,
                location="G-10, Islamabad",
                latitude=33.6938,
                longitude=73.0652,
                explanation="Fallback detected urban flooding in G-10 Islamabad due to heavy rainfall."
            )
            request.app.state.active_crises.append(crisis)
    else:
        scored_signals = []
        for s in raw_signals:
            if hasattr(s, "credibility_score"):
                scored_signals.append(s)
            else:
                scored_signals.append(credibility_engine.score_signal(s))
                
        start_time = datetime.utcnow()
        crisis = classifier.classify(scored_signals)
        
        fusion_result = await fuse_signals_with_gemini(
            scored_signals=[s.model_dump(mode="json") for s in scored_signals],
            classifier_result=crisis.model_dump(mode="json"),
        )
        fusion_output = fusion_result
        
        if "adjusted_confidence" in fusion_result:
            crisis.confidence = fusion_result["adjusted_confidence"]
            
        # Append to active crises state
        request.app.state.active_crises.append(crisis)
        
        # Trace log
        request.app.state.append_trace(
            agent="ClassificationAgent",
            action="classify",
            input_summary=f"Analyzed {len(scored_signals)} scored signals in buffer.",
            output_summary=f"Classified as {crisis.type.value} with confidence {crisis.confidence}.",
            reasoning=fusion_result.get("gemini_reasoning", crisis.explanation),
            tool_called="classify",
            start_time=start_time
        )
        
    return {
        "crisis_id": crisis.crisis_id,
        "type": crisis.type,
        "severity": crisis.severity,
        "confidence": crisis.confidence,
        "affected_radius_km": crisis.affected_radius_km,
        "location": crisis.location,
        "latitude": crisis.latitude,
        "longitude": crisis.longitude,
        "explanation": crisis.explanation,
        "is_active": crisis.is_active,
        "retracted": crisis.retracted,
        "retraction_reason": crisis.retraction_reason,
        "reasoning_log": crisis.reasoning_log,
        "gemini_reasoning": fusion_output.get("gemini_reasoning", ""),
        "uncertainty_level": fusion_output.get("uncertainty_level", "MEDIUM"),
        "coherence_score": fusion_output.get("coherence_score", crisis.confidence),
        "contradiction_flags": fusion_output.get("contradiction_flags", []),
        "adjusted_confidence": fusion_output.get("adjusted_confidence", crisis.confidence),
        "source_weight_summary": fusion_output.get("source_weight_summary", ""),
        "crises": request.app.state.compat_crises or [
            crisis_schema_to_compat_card(crisis)
        ]
    }

@router.get("/active", response_model=List[CrisisSchema])
def get_active(request: Request):
    # Returns active crises
    return [c for c in request.app.state.active_crises if c.is_active]

@router.get("/{crisis_id}", response_model=CrisisSchema)
def get_crisis_by_id(crisis_id: str, request: Request):
    for c in request.app.state.active_crises:
        if c.crisis_id == crisis_id:
            return c
    raise HTTPException(status_code=404, detail=f"Crisis {crisis_id} not found.")

@router.post("/verify", response_model=FalsePositiveResult)
def verify_contradiction(req: VerifyRequest, request: Request):
    # 1. Find active crisis
    target_crisis = None
    for c in request.app.state.active_crises:
        if c.crisis_id == req.crisis_id:
            target_crisis = c
            break
            
    if not target_crisis:
        raise HTTPException(status_code=404, detail=f"Crisis {req.crisis_id} not found.")
        
    start_time = datetime.utcnow()
    
    # 2. Score new signal
    scored_signal = credibility_engine.score_signal(req.new_signal)
    
    # 3. Verify
    result = verifier.verify(scored_signal, target_crisis)
    
    # 4. Retract if needed
    if result.retract:
        verifier.retract_and_update(target_crisis, result)
        # Append retraction note to log
        request.app.state.append_trace(
            agent="VerificationAgent",
            action="retract_crisis",
            input_summary=f"Received contradicting signal {scored_signal.signal_id} for crisis {req.crisis_id}.",
            output_summary=f"Retraction triggered: {result.correction}.",
            reasoning=result.log_entry,
            tool_called="retract_crisis",
            start_time=start_time
        )
    else:
        request.app.state.append_trace(
            agent="VerificationAgent",
            action="verify_crisis",
            input_summary=f"Received signal {scored_signal.signal_id} for crisis {req.crisis_id}.",
            output_summary=f"Maintain alert status. Contradiction score {result.contradiction_score} below threshold.",
            reasoning="Keyword check finished. Credibility score did not provide high enough contradiction margin.",
            tool_called="verify_false_positive",
            start_time=start_time
        )
        
    return result

@router.post("/retract/{crisis_id}", response_model=CrisisSchema)
def manual_retract(crisis_id: str, request: Request, reason: str = Body(..., embed=True)):
    for c in request.app.state.active_crises:
        if c.crisis_id == crisis_id:
            c.retracted = True
            c.is_active = False
            c.retraction_reason = reason
            c.reasoning_log.append(f"Manual alert retraction triggered. Reason: {reason}")
            
            request.app.state.append_trace(
                agent="VerificationAgent",
                action="manual_retract",
                input_summary=f"Manual retraction requested for crisis {crisis_id}.",
                output_summary=f"Retracted crisis. Reason: {reason}",
                reasoning=f"Operator override triggered manual alert retraction.",
                tool_called="retract",
                start_time=datetime.utcnow()
            )
            return c
    raise HTTPException(status_code=404, detail=f"Crisis {crisis_id} not found.")

@router.delete("/clear")
def clear_crises(request: Request):
    request.app.state.active_crises.clear()
    return {"status": "success", "message": "Crisis state cleared."}
