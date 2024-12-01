from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import traceback
from .routes import router
from ..core.config import get_settings
from ..core.sawmill_manager import SawmillManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
    "*"
]

app = FastAPI(
    title="Sawmill Edge API",
    description="API for industrial sawmill control and monitoring",
    version="1.0.0",
    debug=True
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    sawmill_manager = SawmillManager()
    app.state.sawmill_manager = sawmill_manager
    
    try:
        await sawmill_manager.start()
        logger.info("SawmillManager started successfully")
        yield
    except Exception as e:
        logger.error(f"Error during application lifecycle: {e}")
        raise
    finally:
        await sawmill_manager.stop()
        logger.info("SawmillManager stopped successfully")

app.router.lifespan_context = lifespan

# Include routes with prefix - FIXED
settings = get_settings()
prefix = settings.API_PREFIX.rstrip('/')  # Rimuove lo slash finale se presente
app.include_router(router, prefix=prefix)

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI application starting up")
    logger.info(f"CORS configuration enabled for origins: {ALLOWED_ORIGINS}")
    logger.info(f"API prefix: {prefix}")