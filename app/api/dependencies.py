from fastapi import Request, HTTPException
from typing import Annotated
from ..core.sawmill_manager import SawmillManager


async def get_sawmill_manager(request: Request) -> SawmillManager:
    """
    Dependency injection for SawmillManager.
    Verifica che il manager sia inizializzato e connesso.
    """
    manager = request.app.state.sawmill_manager
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="SawmillManager not initialized"
        )

    # Verifica connessioni
    if not manager.opcua_handler.is_connected:
        raise HTTPException(
            status_code=503,
            detail="OPC UA connection not available"
        )

    return manager


# Type annotation per il dependency injection
SawmillManagerDep = Annotated[SawmillManager, get_sawmill_manager]