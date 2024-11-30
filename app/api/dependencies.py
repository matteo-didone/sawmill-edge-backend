# app/api/dependencies.py
from fastapi import Request

async def get_sawmill_manager(request: Request):
    manager = request.app.state.sawmill_manager
    if manager is None:
        raise RuntimeError("SawmillManager not initialized")
    return manager