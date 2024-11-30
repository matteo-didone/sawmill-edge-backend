import asyncio
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

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
        self.mqtt_client = MQTTClient(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)
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
        
        # Task handles
        self.monitoring_task = None
        self.alarm_monitoring_task = None

    async def start(self):
        """Initialize and start all services."""
        try:
            # Load parameter configuration
            self.parameter_system.load_configuration("config/parameters.yaml")

            # Connect to services
            if not await self.opcua_handler.connect():
                self.logger.error("Failed to connect to OPC UA server")
            
            if not await self.mqtt_handler.connect():
                self.logger.error("Failed to connect to MQTT broker")

            # Start monitoring tasks
            self.monitoring_task = asyncio.create_task(self._monitor_machine())
            self.alarm_monitoring_task = asyncio.create_task(self.command_handler.monitor_alarms())

            # Register MQTT command handler
            await self.mqtt_client.add_topic_callback("sawmill/commands", self._handle_mqtt_command, qos=1)

            self.logger.info("SawmillManager started successfully")

        except Exception as e:
            self.logger.error(f"Error starting SawmillManager: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop all services and disconnect."""
        try:
            # Cancel monitoring tasks
            if self.monitoring_task:
                self.monitoring_task.cancel()
            if self.alarm_monitoring_task:
                self.alarm_monitoring_task.cancel()

            # Disconnect from services
            if self.opcua_handler.is_connected:
                await self.opcua_handler.disconnect()
            if self.mqtt_handler.is_connected:
                await self.mqtt_handler.disconnect()

            self.logger.info("SawmillManager stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping SawmillManager: {e}")

    async def _monitor_machine(self):
        """Monitor machine status and publish updates."""
        while True:
            try:
                # Check connections
                if not self.opcua_handler.is_connected:
                    await self.opcua_handler.connect()
                    await asyncio.sleep(5)
                    continue

                if not self.mqtt_handler.is_connected:
                    await self.mqtt_handler.connect()
                    await asyncio.sleep(5)
                    continue

                # Get current status (no need to update, it's handled by subscriptions)
                status = self.opcua_client.get_machine_status()

                # Update parameters
                for name, value in status.items():
                    if name in self.parameter_system.parameters:
                        validated_value = self.validator.validate_parameter_value(
                            name, value, self.parameter_system.parameters[name].data_type
                        )
                        if validated_value is not None:
                            self.parameter_system.update_value(name, validated_value)

                # Publish status if MQTT is connected
                if self.mqtt_handler.is_connected:
                    await self.mqtt_client.publish(
                        self.mqtt_client.topics["status"], 
                        status,
                        qos=1
                    )

                # Process alarms
                active_alarms = self.command_handler.get_active_alarms()
                if active_alarms and self.mqtt_handler.is_connected:
                    await self.mqtt_client.publish(
                        self.mqtt_client.topics["alarm"],
                        [alarm.dict() for alarm in active_alarms],
                        qos=2
                    )

                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in machine monitoring: {e}")
                await asyncio.sleep(5)
    
    async def _handle_mqtt_command(self, topic: str, payload: Dict[str, Any]):
        """Handle commands received via MQTT."""
        try:
            validated_payload = self.validator.validate_mqtt_message(topic, payload)
            if not validated_payload:
                return

            command = MachineCommand(validated_payload.get("command"))
            params = self.validator.sanitize_input(validated_payload.get("params", {}))

            success = await self.command_handler.execute_command(command, params)

            result = {
                "command": command.value,
                "success": success,
                "timestamp": datetime.now().isoformat()
            }

            if self.mqtt_handler.is_connected:
                await self.mqtt_client.publish(
                    self.mqtt_client.topics["control"],
                    result,
                    qos=1
                )

        except Exception as e:
            self.logger.error(f"Error handling MQTT command: {e}")
            error_result = {
                "command": payload.get("command"),
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            if self.mqtt_handler.is_connected:
                await self.mqtt_client.publish(
                    self.mqtt_client.topics["control"],
                    error_result,
                    qos=1
                )

    async def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bool:
        """Execute a machine command through the API."""
        try:
            return await self.command_handler.execute_command(MachineCommand(command), params)
        except Exception as e:
            self.logger.error(f"Error executing command via API: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current machine status."""
        status = self.opcua_client.get_machine_status()
        processed_metrics = self.data_processor.get_processed_metrics()
        
        status.update({
            'metrics': {
                'average_consumption': processed_metrics.average_consumption,
                'average_cutting_speed': processed_metrics.average_cutting_speed,
                'efficiency_rate': processed_metrics.efficiency_rate,
                'pieces_per_hour': processed_metrics.pieces_per_hour,
                'total_pieces': processed_metrics.total_pieces,
                'uptime_percentage': processed_metrics.uptime_percentage,
                'active_time': str(processed_metrics.active_time)
            }
        })
        return status

    def get_alarms(self) -> List[AlarmNotification]:
        """Get current active alarms."""
        return self.command_handler.get_active_alarms()

    async def acknowledge_alarm(self, alarm_code: str) -> bool:
        """Acknowledge a specific alarm."""
        return await self.command_handler.acknowledge_alarm(alarm_code)

    def get_metrics(self) -> ProcessedMetrics:
        """Get current processed metrics."""
        return self.data_processor.get_processed_metrics()

    async def reset_metrics(self):
        """Reset all metrics calculations."""
        self.data_processor.reset()