from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, List, Any
from datetime import datetime
import logging
import json
from ..core.sawmill_manager import SawmillManager
from .dependencies import get_sawmill_manager
from .models import (
    MachineStatus,
    AlarmNotification,
    CommandRequest,
    CommandResponse,
    ProcessedMetricsResponse,
    AlarmSeverity,
    ConfigUpdateRequest
)
from ..core.config import get_settings, update_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=MachineStatus)
async def get_machine_status(
        sawmill: SawmillManager = Depends(get_sawmill_manager)
) -> MachineStatus:
    """Get current machine status."""
    try:
        status = sawmill.get_status()
        return MachineStatus(
            is_active=bool(status.get("is_active", False)),
            is_working=bool(status.get("is_working", False)),
            is_stopped=bool(status.get("is_stopped", True)),
            has_alarm=bool(status.get("has_alarm", False)),
            has_error=bool(status.get("has_error", False)),
            cutting_speed=float(status.get("cutting_speed", 0.0)),
            power_consumption=float(status.get("power_consumption", 0.0)),
            pieces_count=int(status.get("pieces_count", 0))
        )
    except Exception as e:
        logger.error(f"Error getting machine status: {e}")
        raise HTTPException(
            status_code=500,
            detail={"message": str(e), "status": "error"}
        )


@router.get("/alarms", response_model=List[AlarmNotification])
async def get_alarms(
        sawmill: SawmillManager = Depends(get_sawmill_manager)
) -> List[AlarmNotification]:
    """Get list of active alarms."""
    try:
        alerts = sawmill.get_alarms()
        alarm_notifications = []

        for alert in alerts:
            severity = AlarmSeverity.WARNING
            if isinstance(alert, dict):
                if "error" in alert.get("message", "").lower():
                    severity = AlarmSeverity.ERROR
                elif "critical" in alert.get("message", "").lower():
                    severity = AlarmSeverity.CRITICAL

                alarm_notifications.append(AlarmNotification(
                    code=alert.get("code", ""),
                    message=alert.get("message", ""),
                    severity=severity,
                    timestamp=datetime.now() if not alert.get("timestamp") else datetime.fromisoformat(
                        alert["timestamp"]),
                    acknowledged=alert.get("acknowledged", False)
                ))

        return alarm_notifications
    except Exception as e:
        logger.error(f"Error getting alarms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=ProcessedMetricsResponse)
async def get_metrics(
        sawmill: SawmillManager = Depends(get_sawmill_manager)
) -> ProcessedMetricsResponse:
    """Get current processed metrics."""
    try:
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
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/command", response_model=CommandResponse)
async def execute_command(
        command: CommandRequest,
        sawmill: SawmillManager = Depends(get_sawmill_manager)
) -> CommandResponse:
    """Execute a machine command."""
    try:
        success = await sawmill.execute_command(command.command, command.params)
        return CommandResponse(
            success=success,
            timestamp=datetime.now(),
            message="Command executed successfully" if success else "Command failed"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics")
async def get_diagnostics(
        sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Get diagnostic data from sensors."""
    try:
        sensor_data = await sawmill.get_sensor_data()
        if not sensor_data:
            raise HTTPException(status_code=500, detail="No sensor data available")

        return {
            "temperature": sensor_data.get("temperature", {}).get("value", 0),
            "vibration": sensor_data.get("vibration", {}).get("value", 0),
            "pressure": sensor_data.get("pressure", {}).get("value", 0),
            "motorSpeed": sensor_data.get("speed", {}).get("value", 0),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config(
        sawmill: SawmillManager = Depends(get_sawmill_manager)
) -> Dict[str, Any]:
    """Get current machine configuration."""
    try:
        settings = get_settings()
        config = await settings.get_full_config()
        return config
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_config(
        config: ConfigUpdateRequest,
        sawmill: SawmillManager = Depends(get_sawmill_manager)
) -> Dict[str, Any]:
    """Update machine configuration."""
    try:
        # Valida e aggiorna la configurazione
        config_dict = config.dict()
        config_dict["updatedAt"] = datetime.now().isoformat()

        # Aggiorna le impostazioni
        await update_settings(config_dict)

        # Ricarica la configurazione nel manager
        await sawmill.reload_config()

        return {
            "success": True,
            "message": "Configuration updated successfully",
            "config": config_dict
        }
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))
