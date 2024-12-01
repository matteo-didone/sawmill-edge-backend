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
            self.mqtt_client.on_message = self._handle_mqtt_command

            self.logger.info("SawmillManager started successfully")

        except Exception as e:
            self.logger.error(f"Error starting SawmillManager: {e}")
            await self.stop()
            raise

    async def _establish_connections(self):
        """Establish connections to OPC UA and MQTT with retry logic"""
        retry_count = 0
        max_retries = 5  # Increased from 3 to 5
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
                self.logger.warning(
                    f"Connection attempt {retry_count}/{max_retries} failed: {e}"
                )
                if retry_count < max_retries:
                    await asyncio.sleep(backoff_time)
                    backoff_time = min(backoff_time * 2, 60)  # Exponential backoff, max 60s
                else:
                    self.logger.error("Failed to establish connections after all retries")
                    return False

    async def _monitor_machine(self):
        """Monitor machine status and publish updates with improved error handling."""
        backoff_time = self._connection_retry_delay
        max_backoff = 60  # Maximum backoff of 60 seconds
        
        while self._running:
            try:
                # Connection check with improved error handling
                if not self.opcua_handler.is_connected or not self.mqtt_handler.is_connected:
                    self.logger.warning("Connections lost, attempting to reconnect...")
                    success = await self._establish_connections()
                    if not success:
                        backoff_time = min(backoff_time * 2, max_backoff)
                        self.logger.error(f"Reconnection failed, backing off for {backoff_time}s")
                        await asyncio.sleep(backoff_time)
                        continue
                    else:
                        backoff_time = self._connection_retry_delay  # Reset backoff on success
                        self.logger.info("Connections restored successfully")

                # Get current status with timeout
                try:
                    async with asyncio.timeout(5):  # 5 second timeout for status retrieval
                        status = self.opcua_client.get_machine_status()
                        self.last_successful_monitor = datetime.now()
                except asyncio.TimeoutError:
                    self.logger.error("Timeout while getting machine status")
                    await asyncio.sleep(1)
                    continue

                # Validate and process each parameter
                processed_status = {}
                for name, value in status.items():
                    try:
                        if name in self.parameter_system.parameters:
                            validated_value = self.validator.validate_parameter_value(
                                name, value, self.parameter_system.parameters[name].data_type
                            )
                            if validated_value is not None:
                                processed_status[name] = validated_value
                                self.parameter_system.update_value(name, validated_value)
                    except Exception as e:
                        self.logger.error(f"Error processing parameter {name}: {e}")
                        continue

                # Publish status if we have valid data and MQTT is connected
                if processed_status and self.mqtt_handler.is_connected:
                    try:
                        async with asyncio.timeout(3):  # 3 second timeout for MQTT publish
                            await self.mqtt_client.publish(
                                self.mqtt_client.topics["status"], 
                                processed_status,
                                qos=1
                            )
                    except asyncio.TimeoutError:
                        self.logger.error("Timeout while publishing to MQTT")
                    except Exception as e:
                        self.logger.error(f"Error publishing to MQTT: {e}")

                await asyncio.sleep(1)  # Main monitoring interval
                backoff_time = self._connection_retry_delay  # Reset backoff on successful iteration

            except Exception as e:
                self.logger.error(f"Critical error in machine monitoring: {e}")
                await asyncio.sleep(backoff_time)
                continue

    async def _monitor_alarms(self):
        """Monitor and publish alarms with improved error handling."""
        backoff_time = self._connection_retry_delay
        max_backoff = 60  # Maximum backoff of 60 seconds
        
        while self._running:
            try:
                if not self.opcua_handler.is_connected:
                    await asyncio.sleep(1)
                    continue

                try:
                    async with asyncio.timeout(5):  # 5 second timeout for alarm check
                        active_alarms = self.command_handler.get_active_alarms()
                except asyncio.TimeoutError:
                    self.logger.error("Timeout while checking alarms")
                    await asyncio.sleep(1)
                    continue

                if active_alarms and self.mqtt_handler.is_connected:
                    try:
                        async with asyncio.timeout(3):  # 3 second timeout for MQTT publish
                            await self.mqtt_client.publish(
                                self.mqtt_client.topics["alarm"],
                                [alarm.dict() for alarm in active_alarms],
                                qos=2
                            )
                    except asyncio.TimeoutError:
                        self.logger.error("Timeout while publishing alarms to MQTT")
                    except Exception as e:
                        self.logger.error(f"Error publishing alarms to MQTT: {e}")

                await asyncio.sleep(1)
                backoff_time = self._connection_retry_delay  # Reset backoff on success

            except Exception as e:
                self.logger.error(f"Error in alarm monitoring: {e}")
                await asyncio.sleep(backoff_time)
                backoff_time = min(backoff_time * 2, max_backoff)

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
        try:
            status = self.opcua_client.get_machine_status()
            processed_metrics = self.data_processor.get_processed_metrics()
            
            # Calculate time since last successful monitor
            last_update_delta = datetime.now() - self.last_successful_monitor
            
            connection_status = {
                'opcua_connected': self.opcua_handler.is_connected,
                'mqtt_connected': self.mqtt_handler.is_connected,
                'last_update': self.last_successful_monitor.isoformat(),
                'last_update_seconds_ago': last_update_delta.total_seconds()
            }
            
            metrics = {
                'average_consumption': processed_metrics.average_consumption,
                'average_cutting_speed': processed_metrics.average_cutting_speed,
                'efficiency_rate': processed_metrics.efficiency_rate,
                'pieces_per_hour': processed_metrics.pieces_per_hour,
                'total_pieces': processed_metrics.total_pieces,
                'uptime_percentage': processed_metrics.uptime_percentage,
                'active_time': str(processed_metrics.active_time)
            }
            
            return {
                **status,
                'connections': connection_status,
                'metrics': metrics
            }
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {
                'error': str(e),
                'connections': {
                    'opcua_connected': self.opcua_handler.is_connected,
                    'mqtt_connected': self.mqtt_handler.is_connected,
                    'last_update': self.last_successful_monitor.isoformat(),
                    'last_update_seconds_ago': (datetime.now() - self.last_successful_monitor).total_seconds()
                }
            }

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