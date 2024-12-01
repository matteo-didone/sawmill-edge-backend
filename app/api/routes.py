from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
from datetime import datetime
import logging
import json

from app.core.input_validator import ConfigValidator
from app.core.config import update_settings, get_settings
from ..core.sawmill_manager import SawmillManager
from .dependencies import get_sawmill_manager
from .models import (
    MachineStatus,
    AlarmNotification,
    CommandRequest,
    CommandResponse,
    AlarmAcknowledgeRequest,
    ProcessedMetricsResponse,
    TimeWindowRequest,
    ConfigUpdateRequest
)

logger = logging.getLogger(__name__)
router = APIRouter()

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

@router.post("/alarms/{alarm_code}/acknowledge")
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

@router.get("/config")
async def get_config():
    """Get current configuration"""
    try:
        settings = get_settings()
        config = await settings.get_full_config()
        
        return JSONResponse(
            status_code=200,
            content=config
        )
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get configuration: {str(e)}"
        )

@router.post("/config")
async def update_config(request: Request):
    """Update configuration with detailed error handling and logging"""
    try:
        # Log request details
        logger.info(f"Config update request received: {request.url}")
        
        # Get raw body and parse JSON
        body = await request.body()
        try:
            config_data = json.loads(body)
            logger.info(f"Parsed config data: {config_data}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid JSON format", "detail": str(e)}
            )
        
        # Validate configuration
        try:
            config_validator = ConfigValidator(**config_data)
            validated_config = config_validator.dict()
            logger.info(f"Validation successful: {validated_config}")
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return JSONResponse(
                status_code=422,
                content={"error": "Validation failed", "detail": str(e)}
            )
        
        # Update settings
        try:
            await update_settings(validated_config)
            logger.info("Settings updated successfully")
            
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Configuration updated successfully",
                    "config": validated_config
                }
            )
        except Exception as e:
            logger.error(f"Settings update error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to update settings", "detail": str(e)}
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in update_config: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )

@router.post("/metrics/reset")
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

@router.get("/nodes/{node_name}")
async def read_node(
    node_name: str,
    sawmill: SawmillManager = Depends(get_sawmill_manager)
):
    """Read a specific node value."""
    try:
        value = await sawmill.opcua_client.read_node(node_name)
        if value is None:
            raise HTTPException(status_code=404, detail=f"Node {node_name} not found or failed to read")
        return {"node_name": node_name, "value": value}
    except Exception as e:
        logger.error(f"Error reading node {node_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))