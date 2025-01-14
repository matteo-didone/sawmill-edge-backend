
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from .routes import router
from ..core.config import get_settings
from ..core.sawmill_manager import SawmillManager

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestisce il ciclo di vita del SawmillManager."""
    settings = get_settings()
    # Inizializza SawmillManager
    sawmill_manager = SawmillManager()
    app.state.sawmill_manager = sawmill_manager  # Attach to FastAPI state
    try:
        # Avvia i servizi
        await sawmill_manager.start()
        logger.info("SawmillManager avviato con successo")
        yield
    except Exception as e:
        logger.error(f"Errore durante il ciclo di vita dell'applicazione: {e}")
        raise RuntimeError("Errore di inizializzazione del server")
    finally:
        # Arresta il SawmillManager
        await sawmill_manager.stop()
        logger.info("SawmillManager arrestato con successo")

# Crea l'applicazione FastAPI
app = FastAPI(
    title="Sawmill Edge API",
    description="API per il controllo e il monitoraggio di una segheria industriale",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Sostituisci con origini specifiche in produzione
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Includi le rotte
app.include_router(router, prefix=get_settings().API_PREFIX.rstrip("/"))