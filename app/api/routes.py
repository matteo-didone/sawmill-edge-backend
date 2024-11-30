from fastapi import APIRouter, Request, HTTPException, Depends
from typing import List
from datetime import datetime
from ..core.sawmill_manager import SawmillManager
from .models import (
    MachineStatus,
    MachineCommand,
    AlarmNotification,
    CommandRequest,
    CommandResponse,
    AlarmAcknowledgeRequest,
    ProcessedMetricsResponse,
    TimeWindowRequest
)

router = APIRouter()

# Dependency
async def get_sawmill_manager() -> SawmillManager:
    from .application import sawmill_manager
    if sawmill_manager is None:
        raise RuntimeError("SawmillManager not initialized")
    return sawmill_manager

@router.get("/status", response_model=MachineStatus)
async def get_machine_status(
    sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Get current machine status."""
    return sawmill.get_status()

@router.post("/command", response_model=CommandResponse)
async def execute_command(
    command_request: CommandRequest,
    sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Execute a machine command."""
    try:
        success = await sawmill.execute_command(
            command_request.command,
            command_request.params
        )
        return CommandResponse(
            success=success,
            timestamp=datetime.now(),
            message="Command executed successfully" if success else "Command failed"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alarms", response_model=List[AlarmNotification])
async def get_alarms(
    sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Get list of active alarms."""
    return sawmill.get_alarms()

@router.post("/alarms/{alarm_code}/acknowledge", response_model=CommandResponse)
async def acknowledge_alarm(
    alarm_code: str,
    sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Acknowledge an alarm."""
    success = await sawmill.acknowledge_alarm(alarm_code)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alarm {alarm_code} not found")
    return CommandResponse(
        success=True,
        timestamp=datetime.now(),
        message=f"Alarm {alarm_code} acknowledged"
    )

# Metrics Endpoints
@router.get("/metrics", response_model=ProcessedMetricsResponse)
async def get_metrics(
    sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Get current processed metrics."""
    metrics = sawmill.get_metrics()
    return ProcessedMetricsResponse(
        average_consumption=metrics.average_consumption,
        average_cutting_speed=metrics.average_cutting_speed,
        efficiency_rate=metrics.efficiency_rate,
        pieces_per_hour=metrics.pieces_per_hour,
        total_pieces=metrics.total_pieces,
        uptime_percentage=metrics.uptime_percentage,
        active_time=str(metrics.active_time),
        timestamp=datetime.now()
    )

@router.post("/metrics/reset", response_model=CommandResponse)
async def reset_metrics(
    sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Reset all metrics calculations."""
    await sawmill.reset_metrics()
    return CommandResponse(
        success=True,
        timestamp=datetime.now(),
        message="Metrics reset successfully"
    )

# Config Endpoint
@router.get("/config", response_model=dict)
async def get_config(request: Request):
    """
    Get the current configuration of the system.
    """
    from app.core.config import get_settings
    settings = get_settings()
    return {
        "opcua_server_url": settings.OPCUA_SERVER_URL,
        "mqtt_broker_host": settings.MQTT_BROKER_HOST,
        "mqtt_broker_port": settings.MQTT_BROKER_PORT,
        "api_host": settings.API_HOST,
        "api_port": settings.API_PORT,
        "monitoring_interval": settings.MONITORING_INTERVAL,
        "command_timeout": settings.COMMAND_TIMEOUT,
    }