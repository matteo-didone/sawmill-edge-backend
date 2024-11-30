from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, validator, ValidationError
import json
import logging
from datetime import datetime

class MessageValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_mqtt_message(self, topic: str, payload: Union[str, bytes, Dict]) -> Optional[Dict]:
        """Validate MQTT message format and content"""
        try:
            # Convert payload to dict if it's string or bytes
            if isinstance(payload, (str, bytes)):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    self.logger.error("Invalid JSON format in MQTT message")
                    return None

            if not isinstance(payload, dict):
                self.logger.error("MQTT payload must be a JSON object")
                return None

            # Add timestamp if missing
            if 'timestamp' not in payload:
                payload['timestamp'] = datetime.now().isoformat()

            return payload

        except Exception as e:
            self.logger.error(f"Error validating MQTT message: {str(e)}")
            return None

    def validate_parameter_value(self, parameter_name: str, value: Any, expected_type: str) -> Optional[Any]:
        """Validate parameter value against expected type"""
        try:
            if expected_type == 'int':
                return int(value)
            elif expected_type == 'float':
                return float(value)
            elif expected_type == 'bool':
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes')
                return bool(value)
            elif expected_type == 'str':
                return str(value)
            else:
                self.logger.error(f"Unsupported type {expected_type} for parameter {parameter_name}")
                return None
        except (ValueError, TypeError) as e:
            self.logger.error(f"Invalid value for parameter {parameter_name}: {str(e)}")
            return None

    def sanitize_input(self, value: Any) -> Any:
        """Sanitize input to prevent injection attacks"""
        if isinstance(value, str):
            # Remove any potentially dangerous characters or sequences
            return value.replace(';', '').replace('--', '')
        return value