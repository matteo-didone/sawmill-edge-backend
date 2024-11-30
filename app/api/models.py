# app/api/models.py

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MachineStatus(BaseModel):
    is_active: bool
    is_working: bool
    is_stopped: bool
    has_alarm: bool
    has_error: bool
    cutting_speed: float
    power_consumption: float
    pieces_count: int

class AlarmSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlarmNotification(BaseModel):
    code: str
    message: str
    severity: AlarmSeverity
    timestamp: datetime
    acknowledged: bool = False

class MachineCommand(str, Enum):
    START = "start"
    STOP = "stop"
    EMERGENCY_STOP = "emergency_stop"
    RESET = "reset"
