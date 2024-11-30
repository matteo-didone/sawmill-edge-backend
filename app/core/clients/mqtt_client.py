import asyncio
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

        # Connection status
        self.connected = False

        # Store the event loop reference
        self.loop = asyncio.get_event_loop()

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            self.connected = True
            # Subscribe to topics with registered callbacks
            for topic in self._topic_callbacks.keys():
                client.subscribe(topic, qos=1)
                self.logger.info(f"Subscribed to topic on connect: {topic}")
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
                callback = self._topic_callbacks[topic]
                # Schedule the callback in the event loop
                if asyncio.iscoroutinefunction(callback):
                    asyncio.run_coroutine_threadsafe(callback(topic, payload), self.loop)
                else:
                    callback(topic, payload)

        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON received on topic {msg.topic}")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        if rc != 0:
            self.logger.warning("Unexpected disconnection from MQTT broker")

    async def connect(self) -> bool:
        """Asynchronously connect to the MQTT broker."""
        try:
            await asyncio.to_thread(self.client.connect, self.broker, self.port)
            self.client.loop_start()

            # Wait until connected or timeout after 10 seconds
            try:
                await asyncio.wait_for(self._wait_until_connected(), timeout=10)
                return True
            except asyncio.TimeoutError:
                self.logger.error("MQTT connection timed out")
                self.client.loop_stop()
                return False
        except Exception as e:
            self.logger.error(f"Error connecting to MQTT broker: {e}")
            return False

    async def _wait_until_connected(self):
        """Wait until the client is connected."""
        while not self.connected:
            await asyncio.sleep(0.1)

    async def disconnect(self):
        """Asynchronously disconnect from the MQTT broker."""
        try:
            await asyncio.to_thread(self.client.disconnect)
            self.client.loop_stop()
        except Exception as e:
            self.logger.error(f"Error disconnecting from MQTT broker: {e}")

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

    async def subscribe(self, topic: str, qos: int = 0):
        """Asynchronously subscribe to a topic."""
        try:
            await asyncio.to_thread(self.client.subscribe, topic, qos)
            self.logger.info(f"Subscribed to topic: {topic} with QoS {qos}")
        except Exception as e:
            self.logger.error(f"Error subscribing to topic {topic}: {e}")

    async def add_topic_callback(self, topic: str, callback: Callable, qos: int = 0):
        """Add a callback for a specific topic and subscribe to it."""
        self._topic_callbacks[topic] = callback
        try:
            await self.subscribe(topic, qos)
            self.logger.info(f"Added callback and subscribed to topic: {topic} with QoS {qos}")
        except Exception as e:
            self.logger.error(f"Error adding topic callback for {topic}: {e}")

    async def publish(self, topic: str, message: Any, qos: int = 0):
        """Asynchronously publish a message to a topic."""
        try:
            await asyncio.to_thread(
                self.client.publish,
                topic,
                json.dumps(message),
                qos
            )
            self.logger.info(f"Published message to topic: {topic}")
        except Exception as e:
            self.logger.error(f"Error publishing to topic {topic}: {e}")
