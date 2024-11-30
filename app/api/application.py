# app/api/application.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .routes import router
from ..core.config import get_settings
from ..core.sawmill_manager import SawmillManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global SawmillManager instance
sawmill_manager: SawmillManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifecycle of the SawmillManager."""
    global sawmill_manager
    
    settings = get_settings()
    
    # Initialize SawmillManager
    sawmill_manager = SawmillManager(
        opcua_url=settings.OPCUA_SERVER_URL,
        mqtt_broker=settings.MQTT_BROKER_HOST,
        mqtt_port=settings.MQTT_BROKER_PORT
    )
    
    try:
        # Start services
        await sawmill_manager.start()
        logger.info("SawmillManager started successfully")
        yield
    finally:
        # Cleanup
        if sawmill_manager:
            await sawmill_manager.stop()
            logger.info("SawmillManager stopped successfully")

# Create FastAPI application
app = FastAPI(
    title="Sawmill Edge API",
    description="API for controlling and monitoring industrial sawmill",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix=get_settings().API_PREFIX)

# Dependency for routes
async def get_sawmill_manager() -> SawmillManager:
    if sawmill_manager is None:
        raise RuntimeError("SawmillManager not initialized")
    return sawmill_manager