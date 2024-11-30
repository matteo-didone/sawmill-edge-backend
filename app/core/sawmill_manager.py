# app/core/sawmill_manager.py

import asyncio
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from .clients.opcua_client import OPCUAClient
from .clients.mqtt_client import MQTTClient
from .command_handler import CommandHandler
from app.api.models import MachineCommand, AlarmNotification

class SawmillManager:
    def __init__(self, opcua_url: str, mqtt_broker: str, mqtt_port: int):
        self.logger = logging.getLogger(__name__)
        
        # Initialize clients
        self.opcua_client = OPCUAClient(opcua_url)
        self.mqtt_client = MQTTClient(mqtt_broker, mqtt_port)
        self.command_handler = CommandHandler(self.opcua_client)
        
        # Task handles
        self.monitoring_task = None
        self.alarm_monitoring_task = None
        
    async def start(self):
        """Initialize and start all services."""
        try:
            # Connect to OPC UA server
            if not await self.opcua_client.connect():
                raise Exception("Failed to connect to OPC UA server")

            # Connect to MQTT broker
            await self.mqtt_client.connect()
            
            # Start monitoring tasks
            self.monitoring_task = asyncio.create_task(self._monitor_machine())
            self.alarm_monitoring_task = asyncio.create_task(self.command_handler.monitor_alarms())
            
            # Subscribe to MQTT command topic
            await self.mqtt_client.subscribe("sawmill/commands", self._handle_mqtt_command)
            
            self.logger.info("SawmillManager started successfully")
            
        except Exception as e:
            self.logger.error(f"Error starting SawmillManager: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop all services and clean up."""
        try:
            # Cancel monitoring tasks
            if self.monitoring_task:
                self.monitoring_task.cancel()
            if self.alarm_monitoring_task:
                self.alarm_monitoring_task.cancel()
            
            # Disconnect clients
            await self.opcua_client.disconnect()
            await self.mqtt_client.disconnect()
            
            self.logger.info("SawmillManager stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping SawmillManager: {e}")
            raise

    async def _monitor_machine(self):
        """Monitor machine status and publish updates."""
        while True:
            try:
                # Update machine data
                await self.opcua_client.update_machine_data()
                
                # Get current status
                status = self.opcua_client.get_machine_status()
                
                # Publish status to MQTT
                await self.mqtt_client.publish("sawmill/status", status)
                
                # Check for alarms and publish if any
                active_alarms = self.command_handler.get_active_alarms()
                if active_alarms:
                    await self.mqtt_client.publish(
                        "sawmill/alarms",
                        [alarm.dict() for alarm in active_alarms]
                    )
                
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in machine monitoring: {e}")
                await asyncio.sleep(5)

    async def _handle_mqtt_command(self, topic: str, payload: Dict[str, Any]):
        """Handle commands received via MQTT."""
        try:
            command = MachineCommand(payload.get("command"))
            params = payload.get("params", {})
            
            success = await self.command_handler.execute_command(command, params)
            
            # Publish command result
            result = {
                "command": command.value,
                "success": success,
                "timestamp": datetime.now().isoformat()
            }
            await self.mqtt_client.publish("sawmill/command_results", result)
            
        except Exception as e:
            self.logger.error(f"Error handling MQTT command: {e}")
            await self.mqtt_client.publish("sawmill/command_results", {
                "command": payload.get("command"),
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

    # API Methods
    async def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> bool:
        """Execute a machine command through the API."""
        try:
            return await self.command_handler.execute_command(MachineCommand(command), params)
        except Exception as e:
            self.logger.error(f"Error executing command via API: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current machine status for API."""
        return self.opcua_client.get_machine_status()

    def get_alarms(self) -> List[AlarmNotification]:
        """Get active alarms for API."""
        return self.command_handler.get_active_alarms()

    async def acknowledge_alarm(self, alarm_code: str) -> bool:
        """Acknowledge an alarm through the API."""
        return await self.command_handler.acknowledge_alarm(alarm_code)
