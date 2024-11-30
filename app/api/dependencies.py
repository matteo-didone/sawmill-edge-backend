# app/api/dependencies.py
from fastapi import Request, HTTPException
from ..core.sawmill_manager import SawmillManager
from ..core.clients.opcua_client import OPCUAClient

async def get_sawmill_manager(request: Request) -> SawmillManager:
    manager = request.app.state.sawmill_manager
    if manager is None:
        raise HTTPException(status_code=503, detail="SawmillManager not initialized")
    return manager