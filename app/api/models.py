from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Base Machine Models
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
    UPDATE_SPEED = "update_speed"
    
# Request/Response Models
class CommandRequest(BaseModel):
    command: str
    params: Optional[Dict[str, Any]] = None

class CommandResponse(BaseModel):
    success: bool
    timestamp: datetime
    message: Optional[str] = None

class AlarmAcknowledgeRequest(BaseModel):
    alarm_code: str

class TimeWindowRequest(BaseModel):
    minutes: int = 60  # Default to last hour

class ProcessedMetricsResponse(BaseModel):
    average_consumption: float
    average_cutting_speed: float
    efficiency_rate: float
    pieces_per_hour: float
    total_pieces: int
    uptime_percentage: float
    active_time: str
    timestamp: datetime