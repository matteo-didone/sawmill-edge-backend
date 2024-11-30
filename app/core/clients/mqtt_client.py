import paho.mqtt.client as mqtt
import json
import logging
from typing import Callable, Dict, Any
from asyncio import Queue

class MQTTClient:
    def __init__(self, broker: str = "localhost", port: int = 1883):
        """
        Initialize MQTT client for sawmill communication.
        
        Args:
            broker: MQTT broker address
            port: MQTT broker port
        """
        self.broker = broker
        self.port = port
        self.client = mqtt.Client()
        self.command_queue = Queue()
        
        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Dictionary to store topic callbacks
        self._topic_callbacks: Dict[str, Callable] = {}
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # Define topics
        self.base_topic = "sawmill"
        self.topics = {
            "status": f"{self.base_topic}/status",
            "control": f"{self.base_topic}/control",
            "data": f"{self.base_topic}/data",
            "alarm": f"{self.base_topic}/alarm",
            "error": f"{self.base_topic}/error"
        }

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            # Subscribe to control topics
            client.subscribe([(self.topics["control"], 1)])
        else:
            self.logger.error(f"Failed to connect to MQTT broker with code: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic

            if topic == self.topics["control"]:
                self.command_queue.put_nowait(payload)
                
            if topic in self._topic_callbacks:
                self._topic_callbacks[topic](payload)
                
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON received on topic {msg.topic}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        if rc != 0:
            self.logger.warning("Unexpected disconnection from MQTT broker")

    def connect(self) -> bool:
        """Connect to the MQTT broker."""
        try:
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
            return True
        except Exception as e:
            self.logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()

    def publish_status(self, status: Dict[str, Any]):
        """Publish machine status updates."""
        try:
            self.client.publish(
                self.topics["status"],
                json.dumps(status),
                qos=1
            )
        except Exception as e:
            self.logger.error(f"Error publishing status: {e}")

    def publish_data(self, data: Dict[str, Any]):
        """Publish machine data updates."""
        try:
            self.client.publish(
                self.topics["data"],
                json.dumps(data),
                qos=1
            )
        except Exception as e:
            self.logger.error(f"Error publishing data: {e}")

    def publish_alarm(self, alarm: Dict[str, Any]):
        """Publish alarm notifications."""
        try:
            self.client.publish(
                self.topics["alarm"],
                json.dumps(alarm),
                qos=2  # Using QoS 2 for alarms
            )
        except Exception as e:
            self.logger.error(f"Error publishing alarm: {e}")

    async def get_next_command(self) -> Dict[str, Any]:
        """Get the next command from the command queue."""
        return await self.command_queue.get()

    def add_topic_callback(self, topic: str, callback: Callable):
        """Add a callback for a specific topic."""
        self._topic_callbacks[topic] = callback