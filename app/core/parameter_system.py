from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel
import yaml
import logging
import os

class ParameterType(str, Enum):
    OPCUA = "opcua"
    CALCULATED = "calculated"
    VIRTUAL = "virtual"

class Parameter(BaseModel):
    name: str
    type: ParameterType
    node_id: Optional[str] = None
    mqtt_topic: Optional[str] = None
    enabled: bool = True
    data_type: str
    description: Optional[str] = None
    unit: Optional[str] = None
    monitor: bool = True
    publish: bool = True
    calculation: Optional[str] = None

class ParameterSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.parameters: Dict[str, Parameter] = {}
        self.values: Dict[str, Any] = {}

    def load_configuration(self, config_path: str):
        """Load parameter configuration from a YAML file."""
        try:
            # Verifica se il file esiste
            if not os.path.exists(config_path):
                self.logger.error(f"Configuration file not found at {config_path}")
                self._create_default_config(config_path)
                self.logger.info(f"Created default configuration file at {config_path}")

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            if not config or 'parameters' not in config:
                raise ValueError("Invalid configuration format: missing 'parameters' section")

            parameters_config = config["parameters"]
            for name, param_config in parameters_config.items():
                if not isinstance(param_config, dict):
                    raise ValueError(f"Invalid parameter configuration for '{name}': {param_config}")
                
                # Aggiungi il nome al dizionario dei parametri
                param_config['name'] = name
                
                # Crea e aggiungi il parametro
                try:
                    parameter = Parameter(**param_config)
                    self.parameters[name] = parameter
                except Exception as e:
                    self.logger.error(f"Error creating parameter '{name}': {e}")
                    raise

            self.logger.info(f"Successfully loaded {len(self.parameters)} parameters from {config_path}")

        except Exception as e:
            self.logger.error(f"Error loading parameter configuration: {e}")
            raise

    def _create_default_config(self, config_path: str):
        """Create a default configuration file if none exists."""
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        default_config = {
            "parameters": {
                "is_active": {
                    "type": "opcua",
                    "node_id": "ns=1;s=SawMill/States/IsActive",
                    "data_type": "boolean",
                    "description": "Machine active state",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                }
            }
        }

        with open(config_path, 'w') as f:
            yaml.safe_dump(default_config, f, default_flow_style=False)

    def add_parameter(self, parameter: Parameter):
        """Add new parameter dynamically."""
        if parameter.name in self.parameters:
            self.logger.warning(f"Parameter {parameter.name} already exists, updating.")
        self.parameters[parameter.name] = parameter
        self.logger.info(f"Added/Updated parameter: {parameter.name}")

    def remove_parameter(self, name: str):
        """Remove a parameter."""
        if name in self.parameters:
            del self.parameters[name]
            if name in self.values:
                del self.values[name]
            self.logger.info(f"Removed parameter: {name}")
        else:
            self.logger.warning(f"Tried to remove unknown parameter: {name}")

    def update_value(self, name: str, value: Any):
        """Update parameter value."""
        if name in self.parameters:
            self.values[name] = value
            self.logger.debug(f"Updated value of {name} to {value}")
        else:
            self.logger.warning(f"Attempting to update unknown parameter: {name}")

    def get_value(self, name: str) -> Any:
        """Get parameter value."""
        if name not in self.parameters:
            self.logger.warning(f"Attempting to get value of unknown parameter: {name}")
        return self.values.get(name)

    def get_monitored_parameters(self) -> List[Parameter]:
        """Get list of parameters that should be monitored."""
        return [p for p in self.parameters.values() if p.monitor and p.enabled]

    def get_published_parameters(self) -> List[Parameter]:
        """Get list of parameters that should be published via MQTT."""
        return [p for p in self.parameters.values() if p.publish and p.enabled]

    def get_opcua_nodes(self) -> Dict[str, str]:
        """Get mapping of parameter names to OPC UA node IDs."""
        return {
            name: param.node_id
            for name, param in self.parameters.items()
            if param.type == ParameterType.OPCUA and param.node_id and param.enabled
        }