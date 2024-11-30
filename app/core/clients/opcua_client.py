import asyncio
from asyncua import Client, Node
from asyncua.common.subscription import Subscription
from typing import Dict, Any, Optional, Callable, List
import logging
from datetime import datetime

class OPCUAClient:
    def __init__(self, url: str, reconnect_delay: int = 5):
        self.url = url
        self.client: Optional[Client] = None
        self.subscription: Optional[Subscription] = None
        self.connected = False
        self.reconnect_delay = reconnect_delay
        self.logger = logging.getLogger(__name__)
        
        # Aggiorniamo i nodi per matchare il server
        self.nodes = {
            # States folder
            "is_active": "ns=1;s=SawMill/States/IsActive",
            "is_working": "ns=1;s=SawMill/States/IsWorking",
            "is_stopped": "ns=1;s=SawMill/States/IsStopped",
            # Parameters folder
            "cutting_speed": "ns=1;s=SawMill/Parameters/CuttingSpeed",
            "power_consumption": "ns=1;s=SawMill/Parameters/PowerConsumption",
            # Counters folder
            "pieces_count": "ns=1;s=SawMill/Counters/PiecesCount",
            # Alarms folder
            "has_alarm": "ns=1;s=SawMill/Alarms/HasAlarm",
            "has_error": "ns=1;s=SawMill/Alarms/HasError",
        }
        
        self.subscribed_nodes: Dict[str, Node] = {}
        self.machine_data: Dict[str, Any] = {}
        self.value_handlers: Dict[str, List[Callable]] = {}

    async def connect(self) -> bool:
        """Establishes connection to OPC UA server with automatic retry"""
        while not self.connected:
            try:
                self.client = Client(url=self.url)
                await self.client.connect()
                self.connected = True
                self.logger.info("Connected to OPC UA server")
                await self.setup_subscriptions()
                return True
            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
                await asyncio.sleep(self.reconnect_delay)
        return False

    async def setup_subscriptions(self):
        """Setup subscriptions for all monitored nodes"""
        if not self.client:
            return
        
        try:
            self.subscription = await self.client.create_subscription(
                period=500,  # Ms between updates
                handler=SubHandler(self)
            )
            
            for node_name, node_id in self.nodes.items():
                node = self.client.get_node(node_id)
                handle = await self.subscription.subscribe_data_change(node)
                self.subscribed_nodes[node_name] = handle
                
            self.logger.info("Subscriptions setup complete")
        except Exception as e:
            self.logger.error(f"Subscription setup failed: {e}")

    async def disconnect(self):
        """Safely disconnect from the server"""
        try:
            if self.subscription:
                await self.subscription.delete()
            if self.client:
                await self.client.disconnect()
            self.connected = False
            self.logger.info("Disconnected from OPC UA server")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")

    def add_value_handler(self, node_name: str, handler: Callable):
        """Add a handler for value changes of a specific node"""
        if node_name not in self.value_handlers:
            self.value_handlers[node_name] = []
        self.value_handlers[node_name].append(handler)

    async def write_node(self, node_name: str, value: Any) -> bool:
        """Write value to a specific node"""
        if not self.client or not self.connected:
            return False
            
        try:
            node = self.client.get_node(self.nodes[node_name])
            await node.write_value(value)
            self.machine_data[node_name] = value
            return True
        except Exception as e:
            self.logger.error(f"Error writing to {node_name}: {e}")
            return False

    async def read_node(self, node_name: str) -> Optional[Any]:
        """Read value from a specific node"""
        if not self.client or not self.connected:
            return None
            
        try:
            node = self.client.get_node(self.nodes[node_name])
            value = await node.read_value()
            self.machine_data[node_name] = value
            return value
        except Exception as e:
            self.logger.error(f"Error reading {node_name}: {e}")
            return None

    def get_machine_status(self) -> Dict[str, Any]:
        """Get current machine status"""
        return {
            "is_active": self.machine_data.get("is_active", False),
            "is_working": self.machine_data.get("is_working", False),
            "is_stopped": self.machine_data.get("is_stopped", True),
            "has_alarm": self.machine_data.get("has_alarm", False),
            "has_error": self.machine_data.get("has_error", False),
            "cutting_speed": self.machine_data.get("cutting_speed", 0.0),
            "power_consumption": self.machine_data.get("power_consumption", 0.0),
            "pieces_count": self.machine_data.get("pieces_count", 0)
        }

class SubHandler:
    def __init__(self, client: OPCUAClient):
        self._client = client

    async def datachange_notification(self, node: Node, val: Any, data):
        try:
            # Find node name from node id
            node_id = node.nodeid.to_string()
            node_name = next(
                (name for name, id_ in self._client.nodes.items() if id_ == node_id),
                None
            )
            
            if node_name:
                self._client.machine_data[node_name] = val
                # Notify handlers
                if node_name in self._client.value_handlers:
                    for handler in self._client.value_handlers[node_name]:
                        await handler(val)
        except Exception as e:
            self._client.logger.error(f"Error in datachange notification: {e}")