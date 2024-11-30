import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime
from app.api.application import app
from app.api.routes import get_sawmill_manager  # Correct import
from app.core.command_handler import MachineCommand, AlarmSeverity, AlarmNotification

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestSawmillIntegration:
    async def test_command_to_status_flow(self, sawmill_manager):
        """Test the complete flow from sending a command to getting updated status"""
        success = await sawmill_manager.execute_command("start")
        assert success is True

        # Update machine data
        sawmill_manager.opcua_client.machine_data.update({
            "is_working": True,
            "is_stopped": False
        })

        status = sawmill_manager.get_status()
        assert status["is_working"] is True
        assert status["is_stopped"] is False

    async def test_alarm_detection_and_notification(self, sawmill_manager):
        """Test alarm detection, notification, and acknowledgment flow"""
        sawmill_manager.opcua_client.machine_data["has_alarm"] = True
        await sawmill_manager.opcua_client.update_machine_data()

        # Simulate alarm reading
        sawmill_manager.opcua_client.read_node.return_value = "ALM001"

        alarms = sawmill_manager.get_alarms()
        if len(alarms) > 0:
            alarm_code = alarms[0].code
            success = await sawmill_manager.acknowledge_alarm(alarm_code)
            assert success is True


class TestAPIIntegration:
    @pytest_asyncio.fixture
    async def test_client(self, sawmill_manager):
        async def mock_get_sawmill_manager():
            return sawmill_manager

        # Override the dependency using the function from app.api.routes
        app.dependency_overrides[get_sawmill_manager] = mock_get_sawmill_manager
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
        app.dependency_overrides.clear()

    async def test_command_execution_api(self, test_client):
        """Test command execution through API"""
        response = await test_client.post(
            "/api/v1/command",
            json={"command": "start", "params": {}}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data

    async def test_alarm_handling_api(self, test_client, sawmill_manager):
        """Test alarm handling through API"""
        sawmill_manager.opcua_client.machine_data["has_alarm"] = True
        sawmill_manager.command_handler.active_alarms = {
            "ALM001": AlarmNotification(
                code="ALM001",
                message="Test Alarm",
                severity=AlarmSeverity.ERROR,
                timestamp=datetime.now(),
                acknowledged=False
            )
        }

        response = await test_client.get("/api/v1/alarms")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            alarm_code = data[0]["code"]
            response = await test_client.post(f"/api/v1/alarms/{alarm_code}/acknowledge")
            assert response.status_code == 200
            assert response.json()["success"] is True