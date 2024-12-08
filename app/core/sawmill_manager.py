from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
import logging

from .clients.opcua_client import OPCUAClient
from .clients.mqtt_client import MQTTClient
from .command_handler import CommandHandler
from .connection_handler import ConnectionHandler
from .parameter_system import ParameterSystem
from .input_validator import MessageValidator
from app.api.models import MachineCommand, AlarmNotification
from app.core.config import get_settings
from .data_processor import DataProcessor, ProcessedMetrics


class SawmillManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        settings = get_settings()

        # Initialize systems
        self.parameter_system = ParameterSystem()
        self.validator = MessageValidator()

        # Initialize clients with retry logic
        self.opcua_client = OPCUAClient(settings.OPCUA_SERVER_URL)
        self.mqtt_client = MQTTClient(settings.MQTT_HOST, settings.MQTT_PORT)

        self.command_handler = CommandHandler(self.opcua_client)

        # Initialize connection handlers
        self.opcua_handler = ConnectionHandler(
            connect_func=self.opcua_client.connect,
            disconnect_func=self.opcua_client.disconnect,
            name="OPC UA"
        )

        self.mqtt_handler = ConnectionHandler(
            connect_func=self.mqtt_client.connect,
            disconnect_func=self.mqtt_client.disconnect,
            name="MQTT"
        )

        # Initialize the DataProcessor
        self.data_processor = DataProcessor(window_size=3600)

        # Task handles and state
        self.monitoring_task = None
        self.alarm_monitoring_task = None
        self._running = False
        self._connection_retry_delay = 5  # seconds
        self.last_successful_monitor = datetime.now()

        # Initialize machine state
        self._machine_status = {
            "is_active": False,
            "is_working": False,
            "is_stopped": True,
            "has_alarm": False,
            "has_error": False,
            "cutting_speed": 0.0,
            "power_consumption": 0.0,
            "pieces_count": 0
        }

    async def start(self):
        """Initialize and start all services."""
        try:
            self._running = True

            # Load parameter configuration
            self.parameter_system.load_configuration("config/parameters.yaml")

            # Start monitoring tasks
            self.monitoring_task = asyncio.create_task(self._monitor_machine())
            self.alarm_monitoring_task = asyncio.create_task(self._monitor_alarms())

            # Connect to services
            await self._establish_connections()

            # Configure MQTT callbacks
            self.mqtt_client.on_message = self.handle_mqtt_message

            self.logger.info("SawmillManager started successfully")

        except Exception as e:
            self.logger.error(f"Error starting SawmillManager: {e}")
            await self.stop()
            raise

    async def _establish_connections(self):
        """Establish connections to OPC UA and MQTT with retry logic"""
        retry_count = 0
        max_retries = 5
        backoff_time = self._connection_retry_delay

        while retry_count < max_retries:
            try:
                # Connect to OPC UA
                if not await self.opcua_handler.connect():
                    raise Exception("Failed to connect to OPC UA server")

                # Set up OPC UA value handlers
                self.opcua_client.add_value_handler("power_consumption",
                                                    lambda value: self.data_processor.update_power_consumption(value))
                self.opcua_client.add_value_handler("cutting_speed",
                                                    lambda value: self.data_processor.update_cutting_speed(value))
                self.opcua_client.add_value_handler("pieces_count",
                                                    lambda value: self.data_processor.update_pieces_count(value))

                # Connect to MQTT
                if not await self.mqtt_handler.connect():
                    raise Exception("Failed to connect to MQTT broker")

                self.logger.info("Successfully established all connections")
                return True

            except Exception as e:
                retry_count += 1
                self.logger.warning(f"Connection attempt {retry_count}/{max_retries} failed: {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(backoff_time)
                    backoff_time = min(backoff_time * 2, 60)
                else:
                    self.logger.error("Failed to establish connections after all retries")
                    return False

    async def _monitor_machine(self):
        """Monitor machine status and publish updates."""
        while self._running:
            try:
                if not self.opcua_handler.is_connected:
                    await asyncio.sleep(1)
                    continue

                # Read values from OPC UA
                status_updates = {}
                opcua_values = {
                    "is_active": await self.opcua_client.read_node("ns=2;s=SawMill/States/IsActive"),
                    "is_working": await self.opcua_client.read_node("ns=2;s=SawMill/States/IsWorking"),
                    "is_stopped": await self.opcua_client.read_node("ns=2;s=SawMill/States/IsStopped"),
                    "has_alarm": await self.opcua_client.read_node("ns=2;s=SawMill/Alarms/HasAlarm"),
                    "has_error": await self.opcua_client.read_node("ns=2;s=SawMill/Alarms/HasError"),
                    "cutting_speed": await self.opcua_client.read_node("ns=2;s=SawMill/Parameters/CuttingSpeed"),
                    "power_consumption": await self.opcua_client.read_node(
                        "ns=2;s=SawMill/Parameters/PowerConsumption"),
                    "pieces_count": await self.opcua_client.read_node("ns=2;s=SawMill/Counters/PiecesCount")
                }

                # Update internal state
                for key, value in opcua_values.items():
                    if value is not None:
                        status_updates[key] = value
                        self._machine_status[key] = value
                        self.logger.debug(f"Updated {key} to {value}")

                # Log the current state
                self.logger.info(f"Machine status: {self._machine_status}")

                # Publish to MQTT if connected
                if self.mqtt_handler.is_connected and status_updates:
                    try:
                        await self.mqtt_client.publish(
                            "sawmill/status",
                            self._machine_status,
                            qos=1
                        )
                        self.logger.debug(f"Published status to MQTT: {self._machine_status}")
                    except Exception as e:
                        self.logger.error(f"Failed to publish to MQTT: {e}")

                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in machine monitoring: {e}")
                await asyncio.sleep(1)

    async def _monitor_alarms(self):
        """Monitor and publish alarms."""
        while self._running:
            try:
                if not self.opcua_handler.is_connected:
                    await asyncio.sleep(1)
                    continue

                active_alarms = self.command_handler.get_active_alarms()

                if active_alarms and self.mqtt_handler.is_connected:
                    await self.mqtt_client.publish(
                        "sawmill/alarms",
                        [alarm.dict() for alarm in active_alarms],
                        qos=2
                    )

                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in alarm monitoring: {e}")
                await asyncio.sleep(1)

    async def handle_mqtt_message(self, topic: str, payload: Dict[str, Any]):
        """Handle commands received via MQTT."""
        try:
            validated_payload = self.validator.validate_mqtt_message(topic, payload)
            if not validated_payload:
                return

            if 'command' in validated_payload:
                command = validated_payload["command"]
                params = self.validator.sanitize_input(validated_payload.get("params", {}))

                self.logger.info(f"Received command: {command} with params: {params}")

                success = await self.execute_command(command, params)

                result = {
                    "command": command,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                }

                if self.mqtt_handler.is_connected:
                    await self.mqtt_client.publish(
                        "sawmill/control",
                        result,
                        qos=1
                    )

        except Exception as e:
            self.logger.error(f"Error handling MQTT command: {e}")
            if self.mqtt_handler.is_connected:
                error_result = {
                    "command": payload.get("command"),
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                await self.mqtt_client.publish(
                    "sawmill/control",
                    error_result,
                    qos=1
                )

    async def stop(self):
        """Stop all services and disconnect."""
        self._running = False
        try:
            # Cancel monitoring tasks
            for task in [self.monitoring_task, self.alarm_monitoring_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            # Disconnect from services
            if self.opcua_handler.is_connected:
                await self.opcua_handler.disconnect()
            if self.mqtt_handler.is_connected:
                await self.mqtt_handler.disconnect()

            self.logger.info("SawmillManager stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping SawmillManager: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current machine status."""
        return self._machine_status.copy()

    async def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bool:
        """Execute a machine command."""
        try:
            return await self.command_handler.execute_command(MachineCommand(command), params)
        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            return False

    def get_alarms(self) -> List[AlarmNotification]:
        """Get current active alarms."""
        return self.command_handler.get_active_alarms()

    async def acknowledge_alarm(self, alarm_code: str) -> bool:
        """Acknowledge an alarm."""
        return await self.command_handler.acknowledge_alarm(alarm_code)

    def get_metrics(self) -> ProcessedMetrics:
        """Get current processed metrics."""
        return self.data_processor.get_processed_metrics()

    async def reset_metrics(self):
        """Reset all metrics calculations."""
        self.data_processor.reset()
