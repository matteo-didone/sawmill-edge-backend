import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from app.api.application import app

def configure_cors(app):
    """Configure CORS middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080"],  # Frontend Vue.js URL
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def main():
    """Main entry point for the application."""
    # Carica le configurazioni dall'ambiente
    settings = get_settings()

    # Configura CORS
    configure_cors(app)

    # Avvia il server Uvicorn
    uvicorn.run(
        "app.api.application:app",  # Percorso corretto al file e all'istanza FastAPI
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # Mantieni reload abilitato in fase di sviluppo
        log_level=settings.LOG_LEVEL.lower()  # Configura il livello di log
    )

if __name__ == "__main__":
    main()