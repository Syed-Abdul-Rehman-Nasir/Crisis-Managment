import os
import json
import asyncio
import time
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Fallback to manual .env parsing if python-dotenv is not installed in active environment
    import os
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ[key.strip()] = val.strip()
        except Exception:
            pass


# Import modular components
from models import (
    CrisisSchema, AllocationPlan,
    StakeholderMessages, CrisisType, SeverityLevel, RawSignal, SignalSource
)
from reasoning.resource_model import ResourceInventory
from data.generators import SignalStreamScheduler
from agents.agent_configs import OrchestrationPipeline
from intelligence.verifier import FalsePositiveVerifier
from intelligence.credibility import SignalCredibility
from compat_utils import GEO, crisis_dict_to_compat_card, crisis_schema_to_compat_card

app = FastAPI(title="CIRO - Crisis Intelligence & Response Orchestrator API")

# CORS middleware
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")] if allowed_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def query_live_weather_telemetry():
    # Allow some time for startup to finalize
    await asyncio.sleep(5.0)
    while True:
        try:
            api_key = os.environ.get("OPENWEATHERMAP_API_KEY") or os.environ.get("WEATHER_API_KEY", "invalid_dummy_key")
            
            def set_failed():
                app.state.weather_failed = True
                
            # Perform query in thread pool since urllib is blocking
            await asyncio.to_thread(
                app.state.scheduler.weather_api.get_real_weather,
                "Islamabad",
                api_key,
                set_failed
            )
        except Exception:
            app.state.weather_failed = True
        await asyncio.sleep(30.0)

# Startup event
@app.on_event("startup")
async def startup_event():
    app.state.start_time = datetime.utcnow()
    app.state.inventory = ResourceInventory()
    app.state.scheduler = SignalStreamScheduler()
    app.state.active_crises = []
    app.state.allocation_plans = {}
    app.state.stakeholder_messages_store = {}
    app.state.trace_log = []
    app.state.weather_failed = False
    
    # Pre-computed results for compatibility layer
    app.state.current_scenario = "idle"
    app.state.compat_crises = []
    app.state.compat_allocation = {}
    app.state.compat_reasoning = ""
    app.state.compat_actions = []
    app.state.compat_logs = []
    
    # Start continuous simulation task in background
    demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
    if demo_mode:
        app.state.bg_task = asyncio.create_task(
            app.state.scheduler.generate_continuously("g10_flood", interval_seconds=15.0)
        )
    else:
        app.state.bg_task = None
    
    # Start continuous weather telemetry verification in background
    app.state.weather_telemetry_task = asyncio.create_task(
        query_live_weather_telemetry()
    )

# Helper function to append trace log entries in the required schema
def append_trace_log(agent: str, action: str, input_summary: str, output_summary: str, reasoning: str, tool_called: str, start_time: datetime):
    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    badge_colors = {
        "SignalFusionAgent": "bg-indigo-900 text-indigo-200 border-indigo-700",
        "ClassificationAgent": "bg-red-900 text-red-200 border-red-700",
        "ResourceAllocationAgent": "bg-yellow-900 text-yellow-200 border-yellow-700",
        "ResponsePlanningAgent": "bg-green-900 text-green-200 border-green-700",
        "StakeholderCommunicationAgent": "bg-blue-900 text-blue-200 border-blue-700",
        "VerificationAgent": "bg-purple-900 text-purple-200 border-purple-700",
    }
    
    color = badge_colors.get(agent, "bg-gray-900 text-gray-200 border-gray-700")
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent": agent,
        "action": action,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "reasoning": reasoning,
        "tool_called": tool_called,
        "duration_ms": max(1, duration_ms),
        "step": len(app.state.trace_log) + 1,
        "badge_color": color,
        "message": f"[{action.upper()}] {reasoning}"
    }
    app.state.trace_log.append(log_entry)

# Bind trace helper to app state
app.state.append_trace = append_trace_log

# Timing and Logging Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    return response

# Include modular API routers
from api.signals import router as signals_router
from api.crisis import router as crisis_router
from api.resources import router as resources_router
from api.actions import router as actions_router
from api.alerts import router as alerts_router
from api.debug import router as debug_router

app.include_router(signals_router)
app.include_router(crisis_router)
app.include_router(resources_router)
app.include_router(actions_router)
app.include_router(alerts_router)
app.include_router(debug_router)

# WebSocket connection broadcaster
@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await websocket.accept()
    last_sent_index = 0
    try:
        while True:
            buffer_list = list(app.state.scheduler.buffer)
            new_signals = buffer_list[last_sent_index:]
            for signal in new_signals:
                try:
                    await websocket.send_json(signal.model_dump(mode="json"))
                except (TypeError, ValueError) as e:
                    print(f"WebSocket signal send skipped: {e}")
            last_sent_index = len(buffer_list)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass

@app.get("/health")
def health_check(request: Request):
    uptime = (datetime.utcnow() - request.app.state.start_time).total_seconds()
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime,
        "demo_mode": os.getenv("DEMO_MODE", "true").lower() == "true",
        "active_crises_count": len(request.app.state.active_crises),
        "buffered_signals_count": len(request.app.state.scheduler.buffer)
    }

# Local pipeline execution endpoint (Phase 5 specs)
@app.get("/agents/run")
def run_agent_pipeline(scenario: str = "g10_flood"):
    pipeline = OrchestrationPipeline()
    try:
        result = pipeline.run(scenario)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {str(e)}")

# ==========================================
# FRONTEND BACKWARD-COMPATIBILITY API LAYER
# ==========================================

class TriggerRequest(BaseModel):
    scenario: str

@app.post("/api/trigger")
def compat_trigger(req: TriggerRequest):
    scenario = req.scenario.lower().strip()
    app.state.current_scenario = scenario
    
    if scenario == "idle":
        app.state.inventory.reset_all()
        app.state.active_crises.clear()
        app.state.allocation_plans.clear()
        app.state.stakeholder_messages_store.clear()
        app.state.trace_log.clear()
        app.state.compat_crises = []
        app.state.compat_allocation = {}
        app.state.compat_reasoning = ""
        app.state.compat_actions = []
        app.state.compat_logs = []
        return {"status": "success", "scenario": "idle"}
        
    elif scenario == "g10_flood":
        # Run real algorithmic pipeline
        pipeline = OrchestrationPipeline()
        res = pipeline.run("g10_flood")
        
        from reasoning.allocation_explainer import explain_allocation

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        expl = loop.run_until_complete(explain_allocation(
            crisis=res["crisis"],
            allocation_plan=res["allocation"],
            population=85000,
            competing_crises=[],
        ))

        # Populate compat state
        app.state.active_crises = [CrisisSchema.model_validate(res["crisis"])]
        
        # Add another secondary heatwave crisis to match mock UI expectations
        heatwave_crisis = CrisisSchema(
            crisis_id="gulberg_heatwave",
            type=CrisisType.HEATWAVE,
            severity=SeverityLevel.MEDIUM,
            confidence=0.74,
            affected_radius_km=5.0,
            location="Gulberg, Lahore",
            latitude=GEO["gulberg_lahore"][0],
            longitude=GEO["gulberg_lahore"][1],
            explanation="Gulberg heatwave warning. Temp exceeds 43C."
        )
        app.state.active_crises.append(heatwave_crisis)
        
        # Format compat crises (include coordinates for map)
        app.state.compat_crises = [
            crisis_dict_to_compat_card(
                res["crisis"],
                id="g10_flood",
                type="Urban Flooding",
                location="G-10 Islamabad",
                severity="HIGH",
                time_detected="Just now",
                radius_km=2.4,
                latitude=res["crisis"].get("latitude", GEO["g10"][0]),
                longitude=res["crisis"].get("longitude", GEO["g10"][1]),
            ),
            crisis_schema_to_compat_card(
                heatwave_crisis,
                time_detected="10 mins ago",
            ),
        ]
        
        # Format compat allocations
        app.state.compat_allocation = {
            "G-10 Islamabad (Flooding)": "3 Rescue Teams + 2 Police Units + 2 Water Tankers/Pumps",
            "Gulberg, Lahore (Heatwave)": "1 Medical Outreach Unit"
        }
        app.state.compat_reasoning = res["allocation"]["allocation_reasoning"]
        
        # Format compat actions
        app.state.compat_actions = res["actions"]
        
        # Format logs to match original UI expectations (Badge colors, steps)
        app.state.compat_logs = []
        badge_colors = {
            "SignalFusionAgent": "bg-indigo-900 text-indigo-200 border-indigo-700",
            "ClassificationAgent": "bg-red-900 text-red-200 border-red-700",
            "ResourceAllocationAgent": "bg-yellow-900 text-yellow-200 border-yellow-700",
            "ResponsePlanningAgent": "bg-green-900 text-green-200 border-green-700",
            "StakeholderCommunicationAgent": "bg-blue-900 text-blue-200 border-blue-700",
            "VerificationAgent": "bg-purple-900 text-purple-200 border-purple-700",
            "AntigravityOrchestrator": "bg-emerald-900 text-emerald-200 border-emerald-700",
        }
        for idx, entry in enumerate(res["trace_log"]):
            agent_name = entry["agent"]
            color = badge_colors.get(agent_name, "bg-gray-900 text-gray-200 border-gray-700")
            
            if agent_name == "ResourceAllocationAgent" and expl:
                headline = str(expl.get('headline') or 'ALLOCATION UPDATE').upper()
                msg = f"[{headline}] {expl.get('rationale', '')} {expl.get('tradeoffs', '')}\nNote: {expl.get('confidence_note', '')}"
            else:
                msg = f"[{entry['action'].upper()}] {entry['reasoning']}"
                
            app.state.compat_logs.append({
                "agent": agent_name,
                "step": idx + 1,
                "badge_color": color,
                "message": msg
            })
            
    elif scenario == "false_positive":
        # Run g10 flood pipeline
        pipeline = OrchestrationPipeline()
        res = pipeline.run("g10_flood")
        
        from reasoning.allocation_explainer import explain_allocation

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        expl = loop.run_until_complete(explain_allocation(
            crisis=res["crisis"],
            allocation_plan=res["allocation"],
            population=85000,
            competing_crises=[],
        ))

        # We simulate the verification agent trigger:
        # Inbound contradiction signal
        contradiction_sig = RawSignal(
            source_type=SignalSource.EMERGENCY_CALL,
            content="This is CDA water department. We have a water main burst on 7th avenue G-10, not a natural flood.",
            location="G-10, Islamabad",
            latitude=33.6938,
            longitude=73.0652,
            recency_minutes=1,
            mention_frequency=1,
            geo_precision=0.9
        )
        
        # Score and verify
        scored_sig = SignalCredibility().score_signal(contradiction_sig)
        target_crisis = CrisisSchema.model_validate(res["crisis"])
        target_crisis.crisis_id = "g10_flood" # Align ID
        
        ver_result = FalsePositiveVerifier().verify(scored_sig, target_crisis)
        
        # Trigger retraction
        FalsePositiveVerifier().retract_and_update(target_crisis, ver_result)
        
        # Update state
        app.state.active_crises = [target_crisis]
        
        # Format compat crises (include coordinates for map)
        app.state.compat_crises = [
            crisis_schema_to_compat_card(
                target_crisis,
                id="g10_water_main",
                type="Infrastructure - Water Main Burst",
                location="G-10 Islamabad",
                severity="MEDIUM",
                confidence=0.92,
                time_detected="1 mins ago",
                radius_km=0.5,
                latitude=GEO["g10"][0],
                longitude=GEO["g10"][1],
            ),
            {
                "id": "gulberg_heatwave",
                "type": "Heatwave",
                "location": "Gulberg, Lahore",
                "severity": "MEDIUM",
                "confidence": 0.74,
                "time_detected": "15 mins ago",
                "radius_km": 5.0,
                "latitude": GEO["gulberg_lahore"][0],
                "longitude": GEO["gulberg_lahore"][1],
            },
        ]
        
        app.state.compat_allocation = {
            "G-10 Islamabad (Water Main)": "2 Utility Repair Teams + 1 Police Unit (Rescue teams recalled)",
            "Gulberg, Lahore (Heatwave)": "1 Medical Outreach Unit"
        }
        app.state.compat_reasoning = ver_result.log_entry
        
        app.state.compat_actions = [
            {"action": "Alert WAPDA & CDA to repair main water line at 7th Avenue", "status": "COMPLETED"},
            {"action": "Retract G-10 Urban Flooding Public Advisory", "status": "COMPLETED"},
            {"action": "Reopen Margalla Road normal flow", "status": "IN_PROGRESS"},
            {"action": "Cancel PIMS Hospital trauma standby request", "status": "COMPLETED"}
        ]
        
        # Build trace logs including the verification step
        app.state.compat_logs = []
        badge_colors = {
            "SignalFusionAgent": "bg-indigo-900 text-indigo-200 border-indigo-700",
            "ClassificationAgent": "bg-red-900 text-red-200 border-red-700",
            "ResourceAllocationAgent": "bg-yellow-900 text-yellow-200 border-yellow-700",
            "ResponsePlanningAgent": "bg-green-900 text-green-200 border-green-700",
            "StakeholderCommunicationAgent": "bg-blue-900 text-blue-200 border-blue-700",
            "VerificationAgent": "bg-purple-900 text-purple-200 border-purple-700",
            "AntigravityOrchestrator": "bg-emerald-900 text-emerald-200 border-emerald-700",
        }
        for idx, entry in enumerate(res["trace_log"]):
            agent_name = entry["agent"]
            color = badge_colors.get(agent_name, "bg-gray-900 text-gray-200 border-gray-700")
            
            if agent_name == "ResourceAllocationAgent" and expl:
                headline = str(expl.get('headline') or 'ALLOCATION UPDATE').upper()
                msg = f"[{headline}] {expl.get('rationale', '')} {expl.get('tradeoffs', '')}\nNote: {expl.get('confidence_note', '')}"
            else:
                msg = f"[{entry['action'].upper()}] {entry['reasoning']}"
                
            app.state.compat_logs.append({
                "agent": agent_name,
                "step": idx + 1,
                "badge_color": color,
                "message": msg
            })
            
        # Add VerificationAgent retraction log
        app.state.compat_logs.append({
            "agent": "VerificationAgent",
            "step": len(app.state.compat_logs) + 1,
            "badge_color": "bg-purple-900 text-purple-200 border-purple-700",
            "message": f"Contradiction score: {ver_result.contradiction_score} (above threshold 0.6). RETRACTING flood alert. Updating classification to: Infrastructure - Water Main Burst. Public retraction broadcast."
        })

    elif scenario in ["balochistan_earthquake", "karachi_industrial_fire", "lahore_smog_health_crisis"]:
        pipeline = OrchestrationPipeline()
        res = pipeline.run(scenario)
        
        from reasoning.allocation_explainer import explain_allocation

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        expl = loop.run_until_complete(explain_allocation(
            crisis=res["crisis"],
            allocation_plan=res["allocation"],
            population=85000,
            competing_crises=[],
        ))
        
        app.state.active_crises = [CrisisSchema.model_validate(res["crisis"])]
        app.state.compat_crises = [
            crisis_dict_to_compat_card(res["crisis"], time_detected="Just now")
        ]
        app.state.compat_allocation = {
            f"{res['crisis']['location']} ({res['crisis']['type'].title()})": "Standard Response Force"
        }
        app.state.compat_reasoning = res["allocation"]["allocation_reasoning"]
        app.state.compat_actions = res["actions"]
        app.state.compat_logs = []
        badge_colors = {
            "SignalFusionAgent": "bg-indigo-900 text-indigo-200 border-indigo-700",
            "ClassificationAgent": "bg-red-900 text-red-200 border-red-700",
            "ResourceAllocationAgent": "bg-yellow-900 text-yellow-200 border-yellow-700",
            "ResponsePlanningAgent": "bg-green-900 text-green-200 border-green-700",
            "StakeholderCommunicationAgent": "bg-blue-900 text-blue-200 border-blue-700",
            "VerificationAgent": "bg-purple-900 text-purple-200 border-purple-700",
            "AntigravityOrchestrator": "bg-emerald-900 text-emerald-200 border-emerald-700",
        }
        for idx, entry in enumerate(res["trace_log"]):
            agent_name = entry["agent"]
            color = badge_colors.get(agent_name, "bg-gray-900 text-gray-200 border-gray-700")
            if agent_name == "ResourceAllocationAgent" and expl:
                headline = str(expl.get('headline') or 'ALLOCATION UPDATE').upper()
                msg = f"[{headline}] {expl.get('rationale', '')} {expl.get('tradeoffs', '')}\nNote: {expl.get('confidence_note', '')}"
            else:
                msg = f"[{entry['action'].upper()}] {entry['reasoning']}"
                
            app.state.compat_logs.append({
                "agent": agent_name,
                "step": idx + 1,
                "badge_color": color,
                "message": msg
            })
        
    return {"status": "success", "scenario": app.state.current_scenario}

@app.get("/api/trace")
def compat_trace():
    # If trace log is empty, default to idle pre-scripted log to keep page content
    if not app.state.compat_logs:
        return {"logs": []}
    return {"logs": app.state.compat_logs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
