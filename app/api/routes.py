# app/api/routes.py

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from ..core.sawmill_manager import SawmillManager
from .models import MachineStatus, MachineCommand, AlarmNotification

router = APIRouter()

class CommandRequest(BaseModel):
    command: str
    params: Optional[Dict[str, Any]] = None

class CommandResponse(BaseModel):
    success: bool
    timestamp: datetime
    message: Optional[str] = None

class AlarmAcknowledgeRequest(BaseModel):
    alarm_code: str

# Dependency
async def get_sawmill_manager() -> SawmillManager:
    # In a real application, you would get this from your application state
    # This is just a placeholder
    raise NotImplementedError("Implement proper dependency injection")

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