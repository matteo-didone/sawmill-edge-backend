# tests/conftest.py

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from app.core.clients.opcua_client import OPCUAClient
from app.core.clients.mqtt_client import MQTTClient
from app.core.sawmill_manager import SawmillManager
from app.core.command_handler import CommandHandler  # Import CommandHandler here
from app.api.models import MachineCommand, AlarmSeverity, AlarmNotification

@pytest_asyncio.fixture
async def mock_opcua_client():
    client = MagicMock(spec=OPCUAClient)
    # Mock machine data
    client.machine_data = {
        "is_active": False,
        "is_working": False,
        "is_stopped": True,
        "has_alarm": False,
        "has_error": False,
        "cutting_speed": 0,
        "power_consumption": 0,
        "pieces_count": 0
    }

    # Mock methods
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    client.read_node = AsyncMock(return_value=0)
    client.write_node = AsyncMock(return_value=True)
    client.update_machine_data = AsyncMock()
    client.get_machine_status = MagicMock(side_effect=lambda: client.machine_data.copy())
    return client

@pytest_asyncio.fixture
async def mock_mqtt_client():
    client = MagicMock(spec=MQTTClient)
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    return client

@pytest_asyncio.fixture
async def sawmill_manager(mock_opcua_client, mock_mqtt_client):
    manager = SawmillManager("opc.tcp://localhost:4840/freeopcua/server/", "localhost", 1883)
    manager.opcua_client = mock_opcua_client
    manager.mqtt_client = mock_mqtt_client
    manager.command_handler = CommandHandler(mock_opcua_client)

    # Mock the monitoring tasks
    manager.monitoring_task = MagicMock()
    manager.alarm_monitoring_task = MagicMock()

    # Update mock_execute_command to handle active alarms
    async def mock_execute_command(command, params=None):
        if command == MachineCommand.START.value:
            if manager.opcua_client.machine_data["has_alarm"]:
                return False  # Cannot start due to active alarm
            if manager.opcua_client.machine_data["is_working"]:
                return False  # Machine is already working
            manager.opcua_client.machine_data["is_working"] = True
            manager.opcua_client.machine_data["is_stopped"] = False
            return True
        elif command == MachineCommand.EMERGENCY_STOP.value:
            manager.opcua_client.machine_data["is_working"] = False
            manager.opcua_client.machine_data["is_stopped"] = True
            return True
        # Handle other commands as needed
        return False

    manager.execute_command = AsyncMock(side_effect=mock_execute_command)

    # Mock publish_status method
    async def mock_publish_status():
        await manager.mqtt_client.publish("sawmill/status", manager.opcua_client.machine_data)

    manager.publish_status = mock_publish_status

    # Mock handle_mqtt_command method
    async def handle_mqtt_command(topic, payload):
        command = payload.get("command")
        params = payload.get("params", {})
        await manager.execute_command(command, params)

    manager.handle_mqtt_command = handle_mqtt_command

    await manager.start()
    try:
        yield manager
    finally:
        await manager.stop()

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
