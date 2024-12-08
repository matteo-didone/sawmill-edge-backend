from typing import Any, Dict, Optional, Union, List
from pydantic import BaseModel, validator, ValidationError, Field, conint, confloat
from datetime import datetime
import json
import logging
from enum import Enum


class MachineStatus(str, Enum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    STOPPED = "stopped"
    ERROR = "error"


class SafetySettingsValidator(BaseModel):
    tempStop: bool = Field(description="Emergency stop on high temperature")
    maxTemp: confloat(ge=0, le=200) = Field(description="Maximum temperature in Celsius")
    vibrationAlert: bool = Field(description="Enable vibration alerts")
    maxTension: confloat(ge=0, le=100000) = Field(description="Maximum tension in kPa")
    emergencyStopEnabled: bool = Field(description="Enable emergency stop")
    safetyCheckInterval: conint(ge=100, le=10000) = Field(description="Safety check interval in ms")

    @validator('maxTemp')
    def validate_max_temp(cls, v):
        if v <= 0:
            raise ValueError("Maximum temperature must be greater than 0°C")
        return v


class MaintenanceValidator(BaseModel):
    bladeInterval: conint(ge=1, le=1000) = Field(description="Blade change interval in hours")
    nextDate: str = Field(description="Next maintenance date")
    lastMaintenanceDate: Optional[str] = Field(default=None, description="Last maintenance date")
    maintenanceHistory: List[Dict[str, Any]] = Field(default=[], description="Maintenance history")

    @validator('nextDate', 'lastMaintenanceDate')
    def validate_date(cls, v):
        if v is not None:
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError("Invalid date format. Use ISO format (YYYY-MM-DD)")
        return v


class ConfigValidator(BaseModel):
    # Machine Identification
    id: str = Field(description="Machine ID")
    version: str = Field(default="1.0", description="Configuration version")
    status: MachineStatus = Field(default=MachineStatus.ACTIVE, description="Machine status")

    # Connection Settings
    opcua_server_url: str = Field(description="OPC UA Server URL")
    mqtt_host: str = Field(description="MQTT Broker hostname")
    mqtt_port: conint(ge=1, le=65535) = Field(description="MQTT Broker port")
    api_host: str = Field(description="API hostname")
    api_port: conint(ge=1, le=65535) = Field(description="API port")
    monitoring_interval: conint(ge=100, le=60000) = Field(description="Monitoring interval in ms")
    command_timeout: conint(ge=1000, le=30000) = Field(description="Command timeout in ms")

    # Machine Parameters
    bladeSpeed: int = Field(ge=0, le=5000, description="Blade speed in RPM")
    feedRate: int = Field(ge=0, le=2000, description="Feed rate in mm/min")
    cutDepth: int = Field(ge=0, le=500, description="Cut depth in mm")

    # Nested Settings
    safetySettings: SafetySettingsValidator
    maintenance: MaintenanceValidator

    # Metadata
    createdAt: Optional[str] = Field(default=None, description="Creation timestamp")
    updatedAt: Optional[str] = Field(default=None, description="Last update timestamp")

    class Config:
        use_enum_values = True


class MessageValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_config(self, config_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate configuration data using Pydantic model"""
        try:
            validated_config = ConfigValidator(**config_data)
            return validated_config.dict()
        except ValidationError as e:
            self.logger.error(f"Configuration validation error: {e}")
            raise ValueError(str(e))
        except Exception as e:
            self.logger.error(f"Unexpected error during config validation: {e}")
            raise

    def validate_parameter_value(self, name: str, value: Any, data_type: str) -> Optional[Any]:
        """Validate a parameter value based on its expected data type"""
        try:
            if data_type == "boolean":
                return bool(value)
            elif data_type == "float":
                return float(value)
            elif data_type == "integer":
                return int(value)
            elif data_type == "string":
                return str(value)
            else:
                self.logger.warning(f"Unknown data type {data_type} for parameter {name}")
                return value
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error validating parameter {name}: {e}")
            return None

    def validate_mqtt_message(self, topic: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate MQTT message payload"""
        try:
            # Only validate command field for control messages
            if 'control' in topic:
                if 'command' not in payload:
                    self.logger.error("Missing 'command' field in MQTT message")
                    return None

                # Validate command format
                if not isinstance(payload['command'], str):
                    self.logger.error("'command' must be a string")
                    return None

                # Validate params if present
                if 'params' in payload and not isinstance(payload['params'], dict):
                    self.logger.error("'params' must be a dictionary")
                    return None

            return payload
        except Exception as e:
            self.logger.error(f"Error validating MQTT message: {e}")
            return None

    def sanitize_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize input data to prevent injection attacks"""
        sanitized = {}
        for key, value in data.items():
            # Convert key to string and remove any suspicious characters
            safe_key = str(key).replace('../', '').replace('..\\', '')

            # Recursively sanitize dictionaries
            if isinstance(value, dict):
                sanitized[safe_key] = self.sanitize_input(value)
            # Handle lists
            elif isinstance(value, list):
                sanitized[safe_key] = [str(item).replace('../', '').replace('..\\', '')
                                       if isinstance(item, str) else item
                                       for item in value]
            # Handle strings
            elif isinstance(value, str):
                sanitized[safe_key] = value.replace('../', '').replace('..\\', '')
            # Keep other types as is
            else:
                sanitized[safe_key] = value

        return sanitized
