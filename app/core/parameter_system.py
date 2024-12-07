from pathlib import Path
import yaml
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from enum import Enum


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
            # Converti il path in oggetto Path e rendi assoluto se necessario
            config_path = Path(config_path)
            if not config_path.is_absolute():
                # Ottieni il path della root del progetto (2 livelli sopra questo file)
                root_dir = Path(__file__).parent.parent.parent
                config_path = root_dir / config_path

            self.logger.info(f"Loading parameters from: {config_path}")

            # Verifica se il file esiste
            if not config_path.exists():
                self.logger.error(f"Configuration file not found at {config_path}")
                self._create_default_config(config_path)
                self.logger.info(f"Created default configuration file at {config_path}")

            # Leggi il file di configurazione
            config = yaml.safe_load(config_path.read_text())

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

    def _create_default_config(self, config_path: Path):
        """Create a default configuration file with all required parameters."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_config = {
            "parameters": {
                "is_active": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/States/IsActive",
                    "data_type": "boolean",
                    "description": "Machine active state",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                },
                "is_working": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/States/IsWorking",
                    "data_type": "boolean",
                    "description": "Machine working state",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                },
                "is_stopped": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/States/IsStopped",
                    "data_type": "boolean",
                    "description": "Machine stopped state",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                },
                "cutting_speed": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/Parameters/CuttingSpeed",
                    "data_type": "float",
                    "description": "Current cutting speed",
                    "unit": "m/s",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                },
                "power_consumption": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/Parameters/PowerConsumption",
                    "data_type": "float",
                    "description": "Current power consumption",
                    "unit": "kW",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                },
                "pieces_count": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/Counters/PiecesCount",
                    "data_type": "integer",
                    "description": "Number of pieces processed",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                },
                "has_alarm": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/Alarms/HasAlarm",
                    "data_type": "boolean",
                    "description": "Alarm state",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                },
                "has_error": {
                    "type": "opcua",
                    "node_id": "ns=2;s=SawMill/Alarms/HasError",
                    "data_type": "boolean",
                    "description": "Error state",
                    "monitor": True,
                    "publish": True,
                    "enabled": True
                }
            }
        }

        config_path.write_text(yaml.safe_dump(default_config, default_flow_style=False))

    def get_value(self, name: str) -> Any:
        """Get parameter value."""
        if name not in self.parameters:
            self.logger.warning(f"Attempting to get value of unknown parameter: {name}")
            return None

        value = self.values.get(name)
        if value is None:
            param = self.parameters.get(name)
            if param:
                if param.data_type == "boolean":
                    return False
                elif param.data_type == "float":
                    return 0.0
                elif param.data_type == "integer":
                    return 0
        return value

    def update_value(self, name: str, value: Any) -> None:
        """Update parameter value."""
        if name not in self.parameters:
            self.logger.warning(f"Attempting to update unknown parameter: {name}")
            return

        try:
            param = self.parameters[name]

            # Type conversion based on parameter data type
            if param.data_type == "boolean":
                value = bool(value)
            elif param.data_type == "float":
                value = float(value)
            elif param.data_type == "integer":
                value = int(value)

            self.values[name] = value
            self.logger.debug(f"Updated value of {name} to {value}")

        except (ValueError, TypeError) as e:
            self.logger.error(f"Error updating value for {name}: {str(e)}")

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
