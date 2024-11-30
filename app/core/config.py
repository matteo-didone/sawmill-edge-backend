import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from functools import lru_cache
import logging

# Carica il file .env
if not load_dotenv():
    print("WARNING: Could not load .env file")
else:
    print("Loaded .env file")

# Configura il logger
logger = logging.getLogger("config")
logging.basicConfig(level=logging.INFO)

class Settings(BaseSettings):
    # OPC UA Configuration
    OPCUA_SERVER_URL: str = os.getenv("OPCUA_SERVER_URL", "opc.tcp://localhost:4840")
    
    # MQTT Configuration
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = os.getenv("MQTT_USERNAME", "")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD", "")
    MQTT_CLIENT_ID: str = "sawmill_edge"

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1/"  # Valore di default per evitare errori
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"

    # Application Configuration
    MONITORING_INTERVAL: float = 1.0
    COMMAND_TIMEOUT: float = 5.0

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    
    # Log delle configurazioni
    logger.info("Loaded settings:")
    for key, value in settings.dict().items():
        logger.info(f" - {key}: {value}")
    
    return settings
