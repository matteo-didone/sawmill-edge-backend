from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import traceback
from .routes import router
from ..core.config import get_settings
from ..core.sawmill_manager import SawmillManager
from ..core.clients.bridge import OPCUAMQTTBridge

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Configurazione CORS
ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
    "*"
]

# Inizializzazione dell'app
app = FastAPI(
    title="Sawmill Edge API",
    description="API for industrial sawmill control and monitoring",
    version="1.0.0",
    debug=True
)

# Configurazione CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler caught: {exc}")
    logger.error(traceback.format_exc())
    error_msg = str(exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": error_msg
        }
    )

# Debug middleware
@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    try:
        if request.method in ["POST", "PUT"]:
            body = await request.body()
            logger.info(f"Request body: {body.decode()}")
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Error in request: {str(e)}")
        logger.error(traceback.format_exc())
        raise

# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    # Inizializza SawmillManager
    sawmill_manager = SawmillManager()
    app.state.sawmill_manager = sawmill_manager
    
    # Inizializza OPCUAMQTTBridge
    bridge = OPCUAMQTTBridge(
        opcua_url=settings.OPCUA_SERVER_URL,
        mqtt_host=settings.MQTT_HOST,
        mqtt_port=settings.MQTT_PORT
    )
    app.state.bridge = bridge
    
    try:
        # Avvia sia il manager che il bridge
        await sawmill_manager.start()
        await bridge.start()
        logger.info("SawmillManager and Bridge started successfully")
        yield
    except Exception as e:
        logger.error(f"Error during application lifecycle: {e}")
        raise
    finally:
        # Cleanup durante lo shutdown
        await sawmill_manager.stop()
        await bridge.stop()
        logger.info("SawmillManager and Bridge stopped successfully")

# Configura il lifespan context
app.router.lifespan_context = lifespan

# Configura le routes
settings = get_settings()
prefix = settings.API_PREFIX.rstrip('/')  # Rimuove lo slash finale se presente
app.include_router(router, prefix=prefix)

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI application starting up")
    logger.info(f"CORS configuration enabled for origins: {ALLOWED_ORIGINS}")
    logger.info(f"API prefix: {prefix}")