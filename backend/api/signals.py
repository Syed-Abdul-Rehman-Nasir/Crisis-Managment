from fastapi import APIRouter, Request, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from models import RawSignal, ScoredSignal, SignalSource
from intelligence.credibility import SignalCredibility

router = APIRouter(prefix="/api/signals", tags=["signals"])
credibility_engine = SignalCredibility()

class TriggerRequest(BaseModel):
    scenario: str

@router.post("/ingest", response_model=ScoredSignal)
def ingest_signal(request: Request, signal: Optional[Dict[str, Any]] = Body(None)):
    if not signal:
        raise HTTPException(status_code=400, detail="Missing signal payload.")
    try:
        processed = dict(signal)
        
        # Map source_type short form
        src = processed.get("source_type")
        if isinstance(src, str):
            src_clean = src.lower().strip()
            if "social" in src_clean:
                processed["source_type"] = SignalSource.SOCIAL_MEDIA
            elif "weather" in src_clean:
                processed["source_type"] = SignalSource.WEATHER_API
            elif "map" in src_clean:
                processed["source_type"] = SignalSource.GOOGLE_MAPS
            elif "call" in src_clean:
                processed["source_type"] = SignalSource.EMERGENCY_CALL
            elif "history" in src_clean:
                processed["source_type"] = SignalSource.HISTORICAL_DATA
        
        content = processed.get("content", "")
        # Resolve location and coordinates if missing
        if "location" not in processed or not processed.get("location"):
            c_lower = content.lower()
            if "lahore" in c_lower or "gulberg" in c_lower:
                processed["location"] = "Gulberg, Lahore"
                if "latitude" not in processed:
                    processed["latitude"] = 31.5117
                if "longitude" not in processed:
                    processed["longitude"] = 74.3468
            elif "karachi" in c_lower or any(k in c_lower for k in ["clifton", "pechs", "saddar", "korangi"]):
                processed["location"] = "PECHS, Karachi"
                if "latitude" not in processed:
                    processed["latitude"] = 24.8683
                if "longitude" not in processed:
                    processed["longitude"] = 67.0712
            else:
                processed["location"] = "G-10, Islamabad"
                if "latitude" not in processed:
                    processed["latitude"] = 33.6938
                if "longitude" not in processed:
                    processed["longitude"] = 73.0652
                    
        if "latitude" not in processed or processed.get("latitude") is None:
            processed["latitude"] = 33.6938
        if "longitude" not in processed or processed.get("longitude") is None:
            processed["longitude"] = 73.0652
            
        if "recency_minutes" not in processed:
            processed["recency_minutes"] = 5
        if "mention_frequency" not in processed:
            processed["mention_frequency"] = 5
        if "geo_precision" not in processed:
            processed["geo_precision"] = 0.9
            
        signal_obj = RawSignal(**processed)
        scored = credibility_engine.score_signal(signal_obj)
        # Push to buffer
        request.app.state.scheduler.buffer.append(scored)
        
        # Append to trace log helper
        request.app.state.append_trace(
            agent="SignalFusionAgent",
            action="ingest_signal",
            input_summary=f"Ingested raw signal from {signal_obj.source_type.value}.",
            output_summary=f"Scored credibility: {scored.credibility_score}",
            reasoning=f"Computed credibility based on source base and recency factor.",
            tool_called="score_signal",
            start_time=datetime.utcnow()
        )
        return scored
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream", response_model=List[ScoredSignal])
def get_stream(request: Request):
    # Returns last 50 signals
    buf_list = list(request.app.state.scheduler.buffer)[-50:]
    scored_list = []
    for s in buf_list:
        if hasattr(s, "credibility_score"):
            scored_list.append(s)
        else:
            scored_list.append(credibility_engine.score_signal(s))
    return scored_list

@router.post("/trigger", response_model=List[ScoredSignal])
def trigger_scenario(req: TriggerRequest, request: Request):
    scenario = req.scenario.lower().strip()
    scheduler = request.app.state.scheduler
    
    # Get raw signals for scenario
    raw_signals = scheduler.get_scenario_signals(scenario)
    
    # Score them
    scored_signals = credibility_engine.score_batch(raw_signals)
    
    # Empty and reload scheduler buffer with scored signals
    scheduler.buffer.clear()
    for s in scored_signals:
        scheduler.buffer.append(s)
        
    return scored_signals

@router.delete("/clear")
def clear_signals(request: Request):
    request.app.state.scheduler.buffer.clear()
    return {"status": "success", "message": "Signal buffer cleared."}

# Import datetime inside for trace log helper compatibility
from datetime import datetime
