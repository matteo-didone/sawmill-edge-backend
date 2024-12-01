import uvicorn
import asyncio
from app.core.config import get_settings
from app.core.clients.bridge import OPCUAMQTTBridge
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

# Bridge globale che verrà inizializzato durante lo startup
bridge = None

@asynccontextmanager
async def lifespan(app):
    """Gestisce il ciclo di vita dell'applicazione."""
    # Inizializza il bridge durante lo startup
    global bridge
    settings = get_settings()
    
    bridge = OPCUAMQTTBridge(
        opcua_url=settings.OPCUA_SERVER_URL,
        mqtt_host=settings.MQTT_HOST,
        mqtt_port=settings.MQTT_PORT
    )
    
    try:
        # Avvia il bridge in un task separato
        logger.info("Starting OPC UA-MQTT bridge...")
        await bridge.start()
        logger.info("Bridge started successfully")
        yield
    except Exception as e:
        logger.error(f"Error during bridge startup: {e}")
        raise
    finally:
        # Cleanup durante lo shutdown
        if bridge:
            logger.info("Stopping bridge...")
            await bridge.stop()
            logger.info("Bridge stopped successfully")

def main():
    """Main entry point for the application."""
    try:
        # Carica le configurazioni dall'ambiente
        settings = get_settings()
        
        # Configura il logging
        logging.basicConfig(
            level=settings.LOG_LEVEL,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('app.log')
            ]
        )
        
        logger.info("Starting Sawmill Edge application...")
        logger.info(f"API Host: {settings.API_HOST}")
        logger.info(f"API Port: {settings.API_PORT}")
        logger.info(f"OPCUA URL: {settings.OPCUA_SERVER_URL}")
        logger.info(f"MQTT Host: {settings.MQTT_HOST}")
        logger.info(f"MQTT Port: {settings.MQTT_PORT}")
        
        # Avvia il server Uvicorn
        uvicorn.run(
            "app.api.application:app",  # Percorso all'istanza FastAPI
            host=settings.API_HOST,
            port=settings.API_PORT,
            reload=True,  # Mantieni reload abilitato in fase di sviluppo
            log_level=settings.LOG_LEVEL.lower()  # Configura il livello di log
        )
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        raise

if __name__ == "__main__":
    main()