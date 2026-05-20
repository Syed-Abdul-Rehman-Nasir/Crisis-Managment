from fastapi import APIRouter, Request
from datetime import datetime

router = APIRouter(prefix="/api/debug", tags=["debug"])

@router.post("/fail-weather")
def fail_weather(request: Request):
    request.app.state.weather_failed = True
    return {"status": "success", "weather_source": "SIMULATED", "message": "Simulated live weather failover triggered."}

@router.post("/restore-weather")
def restore_weather(request: Request):
    request.app.state.weather_failed = False
    return {"status": "success", "weather_source": "LIVE_OR_MOCK", "message": "Live weather source restored."}

@router.get("/system-status")
def get_system_status(request: Request):
    app_state = request.app.state
    uptime_seconds = (datetime.utcnow() - app_state.start_time).total_seconds()
    
    available_resources = app_state.inventory.get_inventory_summary().get("available_count", 0)
    
    return {
        "api": "healthy",
        "weather_source": "SIMULATED" if getattr(app_state, "weather_failed", False) else "LIVE_OR_MOCK",
        "signal_buffer_size": len(app_state.scheduler.buffer),
        "active_crises": len(app_state.active_crises),
        "resources_available": available_resources,
        "trace_log_entries": len(app_state.trace_log),
        "uptime_seconds": round(uptime_seconds, 2)
    }
