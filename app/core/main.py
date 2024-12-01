import uvicorn
from app.core.config import get_settings

def main():
    """Main entry point for the application."""
    # Carica le configurazioni dall'ambiente
    settings = get_settings()
    
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