from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import traceback
from .routes import router
from ..core.config import get_settings
from ..core.sawmill_manager import SawmillManager

# Configurazione logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Configurazione CORS
ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
]


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione del ciclo di vita dell'applicazione"""
    settings = get_settings()

    # Inizializza SawmillManager
    sawmill_manager = SawmillManager()
    app.state.sawmill_manager = sawmill_manager

    try:
        # Avvia il manager
        await sawmill_manager.start()
        logger.info("SawmillManager started successfully")
        yield
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Cleanup
        if hasattr(app.state, "sawmill_manager"):
            await app.state.sawmill_manager.stop()
            logger.info("SawmillManager stopped successfully")


# Inizializzazione dell'app
app = FastAPI(
    title="Sawmill Edge API",
    description="API for industrial sawmill control and monitoring",
    version="1.0.0",
    debug=True,
    lifespan=lifespan
)

# Configurazione CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Global error handler caught: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc)
        }
    )


@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    """Debug middleware per logging delle richieste"""
    logger.debug(f"Incoming request: {request.method} {request.url}")
    try:
        if request.method in ["POST", "PUT"]:
            body = await request.body()
            logger.debug(f"Request body: {body.decode()}")
        response = await call_next(request)
        logger.debug(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Error in request: {str(e)}")
        logger.error(traceback.format_exc())
        raise


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    manager = request.app.state.sawmill_manager
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "opcua_connected": manager.opcua_handler.is_connected if manager else False,
        "mqtt_connected": manager.mqtt_handler.is_connected if manager else False
    }


# Configura le routes
settings = get_settings()
prefix = settings.API_PREFIX.rstrip('/')
app.include_router(router, prefix=prefix)


# Startup notification
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI application starting up")
    logger.info(f"CORS configuration enabled for origins: {ALLOWED_ORIGINS}")
    logger.info(f"API prefix: {prefix}")
