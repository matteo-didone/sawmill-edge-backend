# app/core/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # OPC UA Configuration
    OPCUA_SERVER_URL: str = "opc.tcp://localhost:4840"
    
    # MQTT Configuration
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    MQTT_CLIENT_ID: str = "sawmill_edge"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    
    # Application Configuration
    MONITORING_INTERVAL: float = 1.0  # seconds
    COMMAND_TIMEOUT: float = 5.0      # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()