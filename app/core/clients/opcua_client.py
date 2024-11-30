import asyncio
from asyncua import Client
from typing import Dict, Any, Optional
import logging

class OPCUAClient:
    def __init__(self, url: str):
        """
        Initialize OPC UA client for sawmill communication.
        
        Args:
            url: The OPC UA server endpoint URL
        """
        self.url = url
        self.client = None
        self.logger = logging.getLogger(__name__)
        
        # Define all required nodes
        self.nodes = {
            "sawtooth": "ns=3;i=1003",  # Already found
            # Machine states
            "machine_state": "ns=3;i=1003",  # To be updated
            "is_active": "ns=3;i=1003",      # To be updated
            "is_working": "ns=3;i=1003",     # To be updated
            "is_stopped": "ns=3;i=1003",     # To be updated
            # Operating parameters
            "cutting_speed": "ns=3;i=1003",  # To be updated
            "power_consumption": "ns=3;i=1003", # To be updated
            "pieces_count": "ns=3;i=1003",   # To be updated
            # Alarms and errors
            "has_alarm": "ns=3;i=1003",      # To be updated
            "has_error": "ns=3;i=1003",      # To be updated
        }
        self.previous_values: Dict[str, Any] = {}
        self.machine_data: Dict[str, Any] = {}

    async def connect(self) -> bool:
        """Connect to the OPC UA server."""
        try:
            self.client = Client(url=self.url)
            await self.client.connect()
            self.logger.info("Connected to OPC UA server")
            return True
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the OPC UA server."""
        if self.client:
            await self.client.disconnect()
            self.logger.info("Disconnected from OPC UA server")

    async def read_node(self, node_id: str) -> Optional[Any]:
        """
        Read value from a specific node.
        
        Args:
            node_id: The node identifier to read
            
        Returns:
            The node value if successful, None otherwise
        """
        try:
            node = self.client.get_node(node_id)
            return await node.read_value()
        except Exception as e:
            self.logger.error(f"Error reading node {node_id}: {e}")
            return None

    async def write_node(self, node_id: str, value: Any) -> bool:
        """
        Write value to a specific node.
        
        Args:
            node_id: The node identifier to write to
            value: The value to write
            
        Returns:
            True if successful, False otherwise
        """
        try:
            node = self.client.get_node(node_id)
            await node.write_value(value)
            self.logger.info(f"Successfully wrote value {value} to node {node_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error writing to node {node_id}: {e}")
            return False

    async def update_machine_data(self):
        """Update all machine data at once."""
        for node_name, node_id in self.nodes.items():
            value = await self.read_node(node_id)
            if value is not None:
                self.machine_data[node_name] = value

    async def monitor_nodes(self):
        """Continuously monitor changes in nodes."""
        while True:
            try:
                for node_name, node_id in self.nodes.items():
                    value = await self.read_node(node_id)
                    if value != self.previous_values.get(node_name):
                        self.logger.info(f"Updated value for {node_name}: {value}")
                        self.previous_values[node_name] = value
                        self.machine_data[node_name] = value
                await asyncio.sleep(1)  # Poll every second
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                break

    def get_machine_status(self) -> Dict[str, Any]:
        """
        Get current machine status.
        
        Returns:
            Dictionary containing current machine status and parameters
        """
        return {
            "is_active": self.machine_data.get("is_active", False),
            "is_working": self.machine_data.get("is_working", False),
            "is_stopped": self.machine_data.get("is_stopped", True),
            "has_alarm": self.machine_data.get("has_alarm", False),
            "has_error": self.machine_data.get("has_error", False),
            "cutting_speed": self.machine_data.get("cutting_speed", 0),
            "power_consumption": self.machine_data.get("power_consumption", 0),
            "pieces_count": self.machine_data.get("pieces_count", 0)
        }