# tests/test_command_handler.py

import pytest
import pytest_asyncio
from datetime import datetime
from app.api.models import AlarmNotification, AlarmSeverity, MachineCommand
from app.core.sawmill_manager import SawmillManager

pytestmark = [pytest.mark.asyncio]

class TestCommandHandler:
    async def test_start_with_active_alarm(self, sawmill_manager):
        """Test that the START command fails if there are active alarms"""

        # Simulate active alarm
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

        # Attempt to start the machine
        success = await sawmill_manager.execute_command("start")
        assert success is False  # Expecting failure due to active alarm

    async def test_emergency_stop(self, sawmill_manager):
        """Test emergency stop command"""

        # Start the machine first
        await sawmill_manager.execute_command("start")

        # Perform emergency stop
        success = await sawmill_manager.execute_command("emergency_stop")
        assert success is True

        # Verify the machine is stopped
        status = sawmill_manager.get_status()
        assert status["is_working"] is False
        assert status["is_stopped"] is True

    async def test_multiple_alarms(self, sawmill_manager):
        """Test handling of multiple alarms"""

        # Simulate multiple alarms
        alarms = [
            AlarmNotification(
                code="ALM001",
                message="Error 1",
                severity=AlarmSeverity.WARNING,
                timestamp=datetime.now(),
                acknowledged=False
            ),
            AlarmNotification(
                code="ALM002",
                message="Error 2",
                severity=AlarmSeverity.ERROR,
                timestamp=datetime.now(),
                acknowledged=False
            )
        ]

        for alarm in alarms:
            sawmill_manager.command_handler.active_alarms[alarm.code] = alarm

        # Verify that all alarms are present
        active_alarms = sawmill_manager.command_handler.get_active_alarms()
        assert len(active_alarms) == 2

        # Acknowledge one alarm
        await sawmill_manager.command_handler.acknowledge_alarm("ALM001")
        assert sawmill_manager.command_handler.active_alarms["ALM001"].acknowledged is True

        # Verify that the other alarm is still unacknowledged
        assert sawmill_manager.command_handler.active_alarms["ALM002"].acknowledged is False

class TestMQTTClient:
    async def test_status_publication(self, sawmill_manager):
        """Test status publication over MQTT"""

        # Update machine status
        sawmill_manager.opcua_client.machine_data.update({
            "is_working": True,
            "cutting_speed": 100
        })

        # Simulate publishing status
        await sawmill_manager.publish_status()

        # Verify that the MQTT client's publish method was called
        sawmill_manager.mqtt_client.publish.assert_called()
        args, kwargs = sawmill_manager.mqtt_client.publish.call_args
        assert args[0] == "sawmill/status"  # Topic
        assert "is_working" in args[1]      # Message payload

    async def test_command_reception(self, sawmill_manager):
        """Test command reception via MQTT"""

        # Simulate received command
        command_data = {
            "command": "start",
            "params": {"speed": 100}
        }

        # Simulate MQTT message handler
        await sawmill_manager.handle_mqtt_command("sawmill/commands", command_data)

        # Verify that the command was executed
        # Since execute_command is an AsyncMock, we can assert it was called
        sawmill_manager.execute_command.assert_called_with("start", {"speed": 100})

        # Alternatively, check the machine status
        status = sawmill_manager.get_status()
        assert status["is_working"] is True
