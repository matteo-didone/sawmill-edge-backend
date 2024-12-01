import os
import json
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache
import logging
from typing import Dict, Any
from datetime import datetime

if not load_dotenv():
    print("WARNING: Could not load .env file")

logger = logging.getLogger("config")
logging.basicConfig(level=logging.INFO)

class MachineConfig:
    CONFIG_FILE = "config/machine_config.json"

    @classmethod
    def ensure_config_dir(cls):
        config_path = Path(cls.CONFIG_FILE)
        config_path.parent.mkdir(exist_ok=True)

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "id": "machine-001",
            "version": "1.0",
            "status": "active",
            "bladeSpeed": 1000,
            "feedRate": 500,
            "cutDepth": 100,
            "safetySettings": {
                "tempStop": True,
                "maxTemp": 80,
                "vibrationAlert": True,
                "maxTension": 45000,
                "emergencyStopEnabled": True,
                "safetyCheckInterval": 1000
            },
            "maintenance": {
                "bladeInterval": 168,
                "nextDate": datetime.now().isoformat(),
                "lastMaintenanceDate": None,
                "maintenanceHistory": []
            },
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        cls.ensure_config_dir()
        config_path = Path(cls.CONFIG_FILE)
        
        if not config_path.exists():
            default_config = cls.get_default_config()
            cls.save_config(default_config)
            return default_config

        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error loading config file: {e}")
            return cls.get_default_config()

    @classmethod
    def save_config(cls, config: Dict[str, Any]):
        cls.ensure_config_dir()
        config_path = Path(cls.CONFIG_FILE)
        
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
            raise

class Settings(BaseSettings):
    # OPC UA Configuration
    OPCUA_SERVER_URL: str = "opc.tcp://localhost:4840/freeopcua/server/"
    
    # MQTT Configuration
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""
    MQTT_CLIENT_ID: str = "sawmill_edge"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"  # Rimosso lo slash finale
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    
    # Application Configuration
    MONITORING_INTERVAL: float = 1.0
    COMMAND_TIMEOUT: float = 5.0

    class Config:
        env_file = ".env"
        case_sensitive = True

    async def get_full_config(self) -> Dict[str, Any]:
        machine_config = MachineConfig.load_config()
        
        return {
            **machine_config,
            "opcua_server_url": self.OPCUA_SERVER_URL,
            "mqtt_broker_host": self.MQTT_BROKER_HOST,
            "mqtt_broker_port": self.MQTT_BROKER_PORT,
            "api_host": self.API_HOST,
            "api_port": self.API_PORT,
            "monitoring_interval": int(self.MONITORING_INTERVAL * 1000),
            "command_timeout": int(self.COMMAND_TIMEOUT * 1000),
        }

    async def update_full_config(self, config: Dict[str, Any]):
        machine_config = MachineConfig.load_config()
        for key, value in config.items():
            if key not in ["opcua_server_url", "mqtt_broker_host", "mqtt_broker_port", 
                        "api_host", "api_port", "monitoring_interval", "command_timeout"]:
                machine_config[key] = value
        
        machine_config["updatedAt"] = datetime.now().isoformat()
        MachineConfig.save_config(machine_config)
        logger.info("Machine configuration updated")

@lru_cache()
def get_settings() -> Settings:
    return Settings()

async def update_settings(config: Dict[str, Any]):
    settings = get_settings()
    await settings.update_full_config(config)