import asyncio
from typing import Optional, Dict, Any, Callable
import json
import logging
from paho.mqtt import client as mqtt


class MQTTClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = int(port)  # Assicurati che la porta sia un intero
        self.client = mqtt.Client()
        self.connected = False
        self.logger = logging.getLogger(__name__)
        self._on_message_callback: Optional[Callable] = None
        self.loop = asyncio.get_event_loop()

        # Keep alive should be longer than the status update interval
        self.client.keepalive = 60

        # Topic configuration
        self.topics = {
            "status": "sawmill/status",  # Semplificato il topic
            "alarm": "sawmill/alarms",
            "control": "sawmill/control",
            "config": "sawmill/config"
        }

        # Set MQTT callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    async def connect(self) -> bool:
        try:
            # Set up last will message
            will_msg = json.dumps({"status": "offline"})
            self.client.will_set(self.topics["status"], will_msg, qos=1, retain=True)

            self.logger.info(f"Connecting to MQTT broker at {self.host}:{self.port}")
            self.client.connect(self.host, self.port)
            self.client.loop_start()

            # Wait for connection
            for attempt in range(10):
                if self.connected:
                    for topic in self.topics.values():
                        self.client.subscribe(topic)
                        self.logger.info(f"Subscribed to topic: {topic}")
                    return True
                await asyncio.sleep(1)
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            self.connected = True
            self.logger.info("Connected to MQTT broker")
        else:
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            error_msg = error_messages.get(rc, f"Unknown error code: {rc}")
            self.logger.error(f"Failed to connect to MQTT broker: {error_msg}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        self.connected = False
        if rc == 0:
            self.logger.info("Cleanly disconnected from MQTT broker")
        else:
            self.logger.warning(f"Unexpected disconnection from MQTT broker with code: {rc}")
            # Trigger reconnection in background
            asyncio.run_coroutine_threadsafe(self.reconnect(), self.loop)

    def _on_message(self, client, userdata, message):
        """Callback for when a message is received"""
        try:
            if not any(topic in message.topic for topic in self.topics.values()):
                return

            try:
                payload = json.loads(message.payload.decode())
            except json.JSONDecodeError:
                self.logger.warning(f"Received invalid JSON on topic {message.topic}")
                return

            # Solo messaggi di controllo richiedono il campo 'command'
            if message.topic == self.topics["control"] and "command" not in payload:
                self.logger.error("Missing 'command' field in control message")
                return

            # Create a task in the event loop to handle the message
            if self._on_message_callback:
                asyncio.run_coroutine_threadsafe(
                    self._on_message_callback(message.topic, payload),
                    self.loop
                )
        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {e}")

    async def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            # Publish disconnected status before disconnecting
            await self.publish(self.topics["status"],
                               {"status": "disconnecting"},
                               qos=1)
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
        except Exception as e:
            self.logger.error(f"Error disconnecting from MQTT broker: {e}")

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> bool:
        """Publish message to MQTT topic"""
        try:
            if not self.connected:
                self.logger.warning("Cannot publish: not connected to MQTT broker")
                return False

            message = json.dumps(payload)
            result = await self.loop.run_in_executor(
                None,
                self.client.publish,
                topic,
                message,
                qos
            )
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"Successfully published to {topic}: {message}")
                return True
            else:
                self.logger.warning(f"Failed to publish to {topic}. RC: {result.rc}")
                return False
        except Exception as e:
            self.logger.error(f"Error publishing to MQTT: {e}")
            return False

    @property
    def on_message(self):
        return self._on_message_callback

    @on_message.setter
    def on_message(self, callback: Callable):
        self._on_message_callback = callback

    async def reconnect(self):
        """Attempt to reconnect to the broker"""
        try:
            if self.connected:
                return True

            # Stop any existing loops
            try:
                self.client.loop_stop()
            except:
                pass

            # Create new client if needed
            if self.client._sock is None:
                self.client = mqtt.Client()
                self.client.on_connect = self._on_connect
                self.client.on_message = self._on_message
                self.client.on_disconnect = self._on_disconnect

            self.logger.info("Attempting to reconnect to MQTT broker...")
            return await self.connect()
        except Exception as e:
            self.logger.error(f"Error during reconnection attempt: {e}")
            return False
