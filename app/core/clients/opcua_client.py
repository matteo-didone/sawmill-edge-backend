import asyncio
from asyncua import Client, Node
from asyncua.common.subscription import Subscription
from typing import Dict, Any, Optional, Callable, List
import logging
from datetime import datetime, timedelta
from asyncua import ua


class OPCUAClient:
    def __init__(self, url: str, reconnect_delay: int = 5):
        self.url = url
        self.client: Optional[Client] = None
        self.subscription: Optional[Subscription] = None
        self.connected = False
        self.reconnect_delay = reconnect_delay
        self.logger = logging.getLogger(__name__)

        # Track subscription handles
        self.subscription_handles: Dict[str, int] = {}
        self.last_subscription_renewal = datetime.now()
        self.subscription_renewal_interval = timedelta(minutes=30)

        # Track connection attempts
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        self.last_connection_attempt = datetime.now()
        self.backoff_time = reconnect_delay

        self.base_nodes = {
            "is_active": "ns=2;s=SawMill/States/IsActive",
            "is_working": "ns=2;s=SawMill/States/IsWorking",
            "is_stopped": "ns=2;s=SawMill/States/IsStopped",
            "cutting_speed": "ns=2;s=SawMill/Parameters/CuttingSpeed",
            "power_consumption": "ns=2;s=SawMill/Parameters/PowerConsumption",
            "pieces_count": "ns=2;s=SawMill/Counters/PiecesCount",
            "has_alarm": "ns=2;s=SawMill/Alarms/HasAlarm",
            "has_error": "ns=2;s=SawMill/Alarms/HasError"
        }

        self.nodes = {}  # Will be populated with correct namespace
        self.subscribed_nodes: Dict[str, Node] = {}
        self.machine_data: Dict[str, Any] = {}
        self.value_handlers: Dict[str, List[Callable]] = {}

    async def _get_namespace_index(self) -> int:
        """Get the correct namespace index from the server."""
        try:
            async with asyncio.timeout(5):
                ns_array = await self.client.get_namespace_array()
                for i, ns in enumerate(ns_array):
                    if "freeopcua.github.io" in ns:
                        self.logger.info(f"Found namespace index {i} for URI: {ns}")
                        return i
                self.logger.warning("Namespace URI not found, available namespaces:")
                for i, ns in enumerate(ns_array):
                    self.logger.warning(f"  {i}: {ns}")
                return 2  # Fallback to what we see in the logs
        except Exception as e:
            self.logger.error(f"Error getting namespace index: {e}")
            return 2

    async def _setup_node_ids(self):
        """Setup node ids with correct namespace index."""
        try:
            # The nodes ids are now fully qualified in the parameters.yaml
            # We'll just copy them directly instead of trying to construct them
            self.nodes = {}
            for name, path in self.base_nodes.items():
                # Remove the path construction and use the node_id directly from parameters
                self.nodes[name] = path

            self.logger.info(f"Node IDs configured with namespace index 2")
            # Log all node IDs for debugging
            for name, node_id in self.nodes.items():
                self.logger.info(f"Node ID - {name}: {node_id}")

        except Exception as e:
            self.logger.error(f"Error setting up node IDs: {e}")
            raise

    async def _verify_node_exists(self, node_id: str) -> bool:
        """Verify if a node exists on the server."""
        try:
            node = self.client.get_node(node_id)
            try:
                await node.read_browse_name()
                return True
            except Exception:
                await node.read_node_class()
                return True
        except Exception as e:
            self.logger.error(f"Node verification failed for {node_id}: {e}")
            return False

    async def connect(self) -> bool:
        """Establishes connection to OPC UA server with automatic retry."""
        if self.connected and self.client:
            return True

        self.connection_attempts += 1
        try:
            self.logger.info(
                f"Attempting connection to OPC UA server ({self.connection_attempts}/{self.max_connection_attempts})")
            self.client = Client(url=self.url)
            self.client.session_timeout = 20000  # 20 seconds timeout
            self.client.secure_channel_timeout = 20000

            async with asyncio.timeout(10):  # 10 seconds connection timeout
                await self.client.connect()

            await self._setup_node_ids()

            test_nodes = ["is_active", "is_working", "cutting_speed"]
            for node_name in test_nodes:
                if not await self._verify_node_exists(self.nodes[node_name]):
                    raise Exception(f"Critical node {node_name} not found on server")

            self.connected = True
            self.connection_attempts = 0  # Reset counter on successful connection
            self.backoff_time = self.reconnect_delay  # Reset backoff
            self.logger.info("Connected to OPC UA server")

            await self.setup_subscriptions()
            return True

        except asyncio.TimeoutError:
            self.logger.error("Connection attempt timed out")
            await self._handle_connection_failure()
            return False
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            await self._handle_connection_failure()
            return False

    async def _handle_connection_failure(self):
        """Handle connection failure with exponential backoff."""
        if self.connection_attempts >= self.max_connection_attempts:
            self.logger.error("Max connection attempts reached")
            self.connection_attempts = 0
            self.backoff_time = self.reconnect_delay
            return

        self.backoff_time = min(self.backoff_time * 2, 60)
        self.last_connection_attempt = datetime.now()

        if self.client:
            try:
                await self.client.disconnect()
            except:
                pass
        self.client = None
        self.connected = False
        self.subscription = None
        self.subscribed_nodes.clear()
        self.subscription_handles.clear()

    async def setup_subscriptions(self):
        """Setup subscriptions for all monitored nodes with error handling."""
        if not self.client or not self.connected:
            return

        try:
            self.subscription = await self.client.create_subscription(
                period=500,  # Ms between updates
                handler=SubHandler(self)
            )

            for node_name, node_id in self.nodes.items():
                try:
                    async with asyncio.timeout(5):
                        node = self.client.get_node(node_id)
                        handle = await self.subscription.subscribe_data_change(node)
                        self.subscribed_nodes[node_name] = node
                        self.subscription_handles[node_name] = handle
                except asyncio.TimeoutError:
                    self.logger.error(f"Timeout subscribing to node {node_name}")
                except Exception as e:
                    self.logger.error(f"Error subscribing to node {node_name}: {e}")

            self.last_subscription_renewal = datetime.now()
            self.logger.info(f"Successfully subscribed to {len(self.subscribed_nodes)} nodes")

        except Exception as e:
            self.logger.error(f"Subscription setup failed: {e}")
            self.subscription = None
            self.subscribed_nodes.clear()
            self.subscription_handles.clear()
            raise

    async def check_subscription_health(self):
        """Check and renew subscriptions if needed."""
        if not self.subscription or not self.connected:
            return

        try:
            if datetime.now() - self.last_subscription_renewal > self.subscription_renewal_interval:
                self.logger.info("Renewing subscriptions...")
                await self.setup_subscriptions()

            if self.subscription.subscription_id:
                try:
                    async with asyncio.timeout(5):
                        await self.subscription.get_state()
                except:
                    self.logger.warning("Subscription appears invalid, recreating...")
                    await self.setup_subscriptions()
        except Exception as e:
            self.logger.error(f"Error checking subscription health: {e}")
            await self.setup_subscriptions()

    async def disconnect(self):
        """Safely disconnect from the server."""
        try:
            if self.subscription:
                await self.subscription.delete()
            if self.client:
                await self.client.disconnect()
            self.connected = False
            self.logger.info("Disconnected from OPC UA server")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
        finally:
            self.client = None
            self.subscription = None
            self.subscribed_nodes.clear()
            self.subscription_handles.clear()

    def add_value_handler(self, node_name: str, handler: Callable):
        """Add a handler for value changes of a specific node."""
        if node_name not in self.value_handlers:
            self.value_handlers[node_name] = []
        self.value_handlers[node_name].append(handler)

    async def write_node(self, node_name: str, value: Any) -> bool:
        """Write value to a specific node with timeout."""
        if not self.client or not self.connected:
            return False

        try:
            async with asyncio.timeout(5):
                node = self.client.get_node(self.nodes[node_name])
                await node.write_value(value)
                self.machine_data[node_name] = value
                return True
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout writing to {node_name}")
            return False
        except Exception as e:
            self.logger.error(f"Error writing to {node_name}: {e}")
            return False

    async def read_node(self, node_id: str) -> Any:
        try:
            self.logger.debug(f"Attempting to read node: {node_id}")
            node = self.client.get_node(node_id)
            value = await node.read_value()
            self.logger.debug(f"Successfully read node {node_id}: {value}")
            return value
        except Exception as e:
            self.logger.error(f"Error reading {node_id}: {str(e)}")
            return None

    def get_machine_status(self) -> Dict[str, Any]:
        """Get current machine status with timestamp."""
        current_time = datetime.now().isoformat()
        return {
            "timestamp": current_time,
            "is_active": self.machine_data.get("is_active", False),
            "is_working": self.machine_data.get("is_working", False),
            "is_stopped": self.machine_data.get("is_stopped", True),
            "has_alarm": self.machine_data.get("has_alarm", False),
            "has_error": self.machine_data.get("has_error", False),
            "cutting_speed": self.machine_data.get("cutting_speed", 0.0),
            "power_consumption": self.machine_data.get("power_consumption", 0.0),
            "pieces_count": self.machine_data.get("pieces_count", 0)
        }

    async def get_sensor_data(self) -> Dict[str, Dict[str, Any]]:
        """Get data from all sensors."""
        if not self.client or not self.connected:
            return {}

        try:
            sensor_data = {}
            sensors = {
                "temperature": "SawMill/Sensors/Temperature",
                "vibration": "SawMill/Sensors/Vibration",
                "pressure": "SawMill/Sensors/Pressure",
                "speed": "SawMill/Sensors/Speed"
            }

            for sensor_id, node_path in sensors.items():
                try:
                    ns_idx = await self._get_namespace_index()
                    node_id = f"ns={ns_idx};s={node_path}"
                    node = self.client.get_node(node_id)
                    value = await node.read_value()

                    sensor_data[sensor_id] = {
                        "value": value,
                        "unit": self._get_sensor_unit(sensor_id),
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    self.logger.error(f"Error reading sensor {sensor_id}: {e}")

            return sensor_data
        except Exception as e:
            self.logger.error(f"Error getting sensor data: {e}")
            return {}

    def _get_sensor_unit(self, sensor_id: str) -> str:
        """Get the unit for a specific sensor."""
        units = {
            "temperature": "°C",
            "vibration": "Hz",
            "pressure": "bar",
            "speed": "rpm"
        }
        return units.get(sensor_id, "")

    async def get_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts and errors."""
        if not self.client or not self.connected:
            return []

        alerts = []
        try:
            has_alarm = await self.read_node("has_alarm")
            has_error = await self.read_node("has_error")

            if has_alarm:
                alerts.append({
                    "severity": "warning",
                    "message": "Machine alarm active",
                    "code": "ALARM_001",
                    "timestamp": datetime.now().isoformat()
                })

            if has_error:
                alerts.append({
                    "severity": "error",
                    "message": "Machine error detected",
                    "code": "ERROR_001",
                    "timestamp": datetime.now().isoformat()
                })

            return alerts
        except Exception as e:
            self.logger.error(f"Error getting alerts: {e}")
            return []


class SubHandler:
    def __init__(self, client: OPCUAClient):
        self._client = client
        self.logger = logging.getLogger(__name__)

    async def datachange_notification(self, node: Node, val: Any, data):
        """Handle data change notifications."""
        try:
            node_id = node.nodeid.to_string()
            node_name = next(
                (name for name, id_ in self._client.nodes.items() if id_ == node_id),
                None
            )

            if node_name:
                self._client.machine_data[node_name] = val
                if node_name in self._client.value_handlers:
                    for handler in self._client.value_handlers[node_name]:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(val)
                            else:
                                handler(val)
                        except Exception as e:
                            self.logger.error(f"Error in value handler for {node_name}: {e}")
        except Exception as e:
            self.logger.error(f"Error in datachange notification: {e}")

    async def status_change_notification(self, status):
        """Handle subscription status changes."""
        self.logger.info(f"Subscription status changed: {status}")

    async def subscription_cancelled(self):
        """Handle subscription cancellation."""
        self.logger.warning("Subscription was cancelled by server")
        if self._client.connected:
            try:
                await self._client.setup_subscriptions()
            except Exception as e:
                self.logger.error(f"Failed to recreate subscription: {e}")
