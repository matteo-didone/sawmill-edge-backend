import asyncio
import logging
from typing import Callable, List, Tuple, Any

class ConnectionHandler:
    def __init__(
        self, 
        connect_func: Callable, 
        disconnect_func: Callable, 
        name: str, 
        max_retries: int = 5
    ):
        self.connect_func = connect_func
        self.disconnect_func = disconnect_func
        self.name = name
        self.max_retries = max_retries
        self.is_connected = False
        self.logger = logging.getLogger(__name__)
        self.reconnection_task = None
        self.message_buffer: List[Tuple[str, Any]] = []

    async def connect(self) -> bool:
        """Attempt to connect with retries."""
        attempt = 0
        while attempt < self.max_retries:
            attempt += 1
            try:
                self.logger.info(f"Attempt {attempt}/{self.max_retries} to connect to {self.name}")
                connected = await self.connect_func()
                
                if connected:
                    self.is_connected = True
                    self.logger.info(f"Successfully connected to {self.name}")
                    return True
                
            except Exception as e:
                self.logger.error(f"Connection attempt to {self.name} failed: {str(e)}")
                await asyncio.sleep(5)
            
            self.logger.error(f"Connection attempt to {self.name} timed out")
        
        return False

    async def disconnect(self):
        """Disconnect from the service."""
        try:
            await self.disconnect_func()
            self.is_connected = False
            self.logger.info(f"Disconnected from {self.name}")
        except Exception as e:
            self.logger.error(f"Error disconnecting from {self.name}: {str(e)}")

    async def start_reconnection_task(self):
        """Start a background task to handle reconnection."""
        if self.reconnection_task is None or self.reconnection_task.done():
            self.reconnection_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self):
        """Handle reconnection attempts."""
        while not self.is_connected:
            if await self.connect():
                self.logger.info(f"Reconnected to {self.name}")
                await self._process_buffered_messages()
                break
            await asyncio.sleep(5)

    def buffer_message(self, message: Tuple[str, Any]):
        """Buffer a message to be sent when connection is restored."""
        self.message_buffer.append(message)
        if len(self.message_buffer) > 1000:  # Prevent buffer overflow
            self.message_buffer = self.message_buffer[-1000:]

    async def _process_buffered_messages(self):
        """Process any messages that were buffered during disconnection."""
        while self.message_buffer and self.is_connected:
            topic, message = self.message_buffer.pop(0)
            try:
                # This assumes the connect_func is from a client that has a publish method
                await self.connect_func.__self__.publish(topic, message)
            except Exception as e:
                self.logger.error(f"Error processing buffered message: {str(e)}")
                self.message_buffer.insert(0, (topic, message))
                break