import asyncio
import logging
from .opcua_client import OPCUAClient
from .mqtt_client import MQTTClient

class OPCUAMQTTBridge:
    def __init__(self, opcua_url: str, mqtt_host: str, mqtt_port: int):
        self.logger = logging.getLogger(__name__)
        self.opcua_client = OPCUAClient(opcua_url)
        self.mqtt_client = MQTTClient(mqtt_host, mqtt_port)
        self._running = False

    async def start(self):
        """Start the bridge"""
        try:
            # Connect both clients
            await self.opcua_client.connect()
            mqtt_connected = await self.mqtt_client.connect()
            if not mqtt_connected:
                self.logger.error("Failed to connect to MQTT broker")
                return
            
            self._running = True
            # Start the publication loops
            await asyncio.gather(
                self._publish_machine_status(),
                self._publish_sensor_data(),
                self._publish_alerts(),
            )
        except Exception as e:
            self.logger.error(f"Error starting bridge: {e}")

    async def stop(self):
        """Stop the bridge"""
        self._running = False
        await self.opcua_client.disconnect()
        await self.mqtt_client.disconnect()

    async def _publish_machine_status(self):
        """Publish machine status data"""
        while self._running:
            try:
                machine_status = self.opcua_client.get_machine_status()
                
                # Convert Python objects to serializable types
                status_payload = {
                    "isActive": bool(machine_status["is_active"]),
                    "isWorking": bool(machine_status["is_working"]),
                    "isStopped": bool(machine_status["is_stopped"]),
                    "cuttingSpeed": float(machine_status["cutting_speed"]),
                    "powerConsumption": float(machine_status["power_consumption"]),
                    "piecesCount": int(machine_status["pieces_count"]),
                    "timestamp": machine_status["timestamp"]
                }
                
                await self.mqtt_client.publish(
                    self.mqtt_client.topics["status"], 
                    status_payload
                )
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                self.logger.error(f"Error publishing machine status: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _publish_sensor_data(self):
        """Publish sensor data to individual topics"""
        while self._running:
            try:
                sensor_data = await self.opcua_client.get_sensor_data()
                for sensor_id, data in sensor_data.items():
                    # Convert to serializable types
                    payload = {
                        "value": float(data["value"]),
                        "unit": str(data["unit"]),
                        "timestamp": data["timestamp"]
                    }
                    await self.mqtt_client.publish(f"{self.mqtt_client.topics['sensors']}/{sensor_id}", 
                                                 payload)
                await asyncio.sleep(0.5)  # Update every 500ms
            except Exception as e:
                self.logger.error(f"Error publishing sensor data: {e}")
                await asyncio.sleep(5)

    async def _publish_alerts(self):
        """Publish alerts and warnings"""
        while self._running:
            try:
                alerts = await self.opcua_client.get_alerts()
                if alerts:
                    for alert in alerts:
                        # Convert to serializable types
                        alert_payload = {
                            "type": str(alert["severity"]),
                            "message": str(alert["message"]),
                            "code": str(alert["code"]),
                            "timestamp": alert["timestamp"]
                        }
                        await self.mqtt_client.publish(
                            self.mqtt_client.topics["alarm"], 
                            alert_payload
                        )
                await asyncio.sleep(0.2)  # Check frequently for alerts
            except Exception as e:
                self.logger.error(f"Error publishing alerts: {e}")
                await asyncio.sleep(5)

    async def handle_config_update(self, config_data: dict):
        """Handle configuration updates from frontend"""
        try:
            # Apply configuration to OPC UA server
            success = await self.opcua_client.update_configuration(config_data)
            
            # Publish confirmation
            status_payload = {
                "status": "success" if success else "error",
                "timestamp": int(asyncio.get_event_loop().time())
            }
            
            if not success:
                status_payload["message"] = "Failed to update configuration"
                
            await self.mqtt_client.publish(
                self.mqtt_client.topics["config"], 
                status_payload
            )
        except Exception as e:
            self.logger.error(f"Error updating configuration: {e}")
            error_payload = {
                "status": "error",
                "message": str(e),
                "timestamp": int(asyncio.get_event_loop().time())
            }
            await self.mqtt_client.publish(
                self.mqtt_client.topics["config"], 
                error_payload
            )