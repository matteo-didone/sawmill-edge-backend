# app/core/main.py

import asyncio
import uvicorn
from api.application import app
from core.config import get_settings

def main():
    """Main entry point for the application."""
    settings = get_settings()
    
    uvicorn.run(
        "api.application:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # Disable in production
        log_level=settings.LOG_LEVEL.lower()
    )

if __name__ == "__main__":
    main()