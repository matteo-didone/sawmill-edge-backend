import asyncio
from typing import Callable, Optional, Any
from datetime import datetime
import logging
from collections import deque

class ConnectionHandler:
    def __init__(
        self, 
        connect_func: Callable,
        disconnect_func: Callable,
        name: str,
        max_retries: int = 5,
        retry_delay: int = 5,
        buffer_size: int = 1000
    ):
        self.logger = logging.getLogger(__name__)
        self.connect_func = connect_func
        self.disconnect_func = disconnect_func
        self.name = name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.is_connected = False
        self.last_connected: Optional[datetime] = None
        self.connection_attempts = 0
        self.message_buffer = deque(maxlen=buffer_size)
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stop_reconnect = False  # State to stop the reconnection task

    def set_connection_state(self, connected: bool):
        """Set the connection state and update the timestamp."""
        self.is_connected = connected
        if connected:
            self.last_connected = datetime.now()
        self.logger.info(f"Connection state set to {connected} for {self.name}")

    async def connect(self) -> bool:
        """Attempt to connect with retry logic."""
        self._stop_reconnect = False  # Reset the stop flag
        self.connection_attempts = 0  # Reset connection attempts
        while self.connection_attempts < self.max_retries and not self._stop_reconnect:
            try:
                self.logger.info(
                    f"Attempt {self.connection_attempts + 1}/{self.max_retries} to connect to {self.name}"
                )
                success = await asyncio.wait_for(self.connect_func(), timeout=10)
                if success:
                    self.set_connection_state(True)
                    self.logger.info(f"Successfully connected to {self.name}")
                    return True
                else:
                    self.logger.error(f"Connection to {self.name} failed")
            except asyncio.TimeoutError:
                self.logger.error(f"Connection attempt to {self.name} timed out")
            except Exception as e:
                self.logger.error(f"Connection attempt failed: {str(e)}")
            
            self.connection_attempts += 1
            if self.connection_attempts < self.max_retries:
                await asyncio.sleep(self.retry_delay)
        
        self.logger.error(f"Failed to connect to {self.name} after {self.max_retries} attempts")
        return False

    async def disconnect(self):
        """Safely disconnect."""
        try:
            await asyncio.wait_for(self.disconnect_func(), timeout=10)
            self.set_connection_state(False)
            self.logger.info(f"Disconnected from {self.name}")
        except asyncio.TimeoutError:
            self.logger.error(f"Disconnection from {self.name} timed out")
        except Exception as e:
            self.logger.error(f"Error during disconnect: {str(e)}")

    def buffer_message(self, message: Any):
        """Store the message in the buffer in case of connection loss."""
        self.message_buffer.append((datetime.now(), message))
        self.logger.debug(f"Message buffered. Buffer size: {len(self.message_buffer)}")

    async def process_buffer(self, process_func: Callable):
        """Process buffered messages upon connection restoration."""
        while self.message_buffer:
            timestamp, message = self.message_buffer.popleft()
            try:
                await process_func(message)
            except Exception as e:
                self.logger.error(f"Error processing buffered message: {str(e)}")
                # Discard old messages or re-add to buffer
                if (datetime.now() - timestamp).seconds > 300:  # 5 minutes
                    self.logger.warning("Discarding old message from buffer")
                else:
                    self.message_buffer.appendleft((timestamp, message))
                    break

    async def start_reconnection_task(self):
        """Start the reconnection task."""
        if not self._reconnect_task or self._reconnect_task.done():
            self._stop_reconnect = False
            self._reconnect_task = asyncio.create_task(self._reconnection_loop())

    async def stop_reconnection_task(self):
        """Stop the reconnection task."""
        self._stop_reconnect = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                self.logger.info(f"Reconnection task for {self.name} stopped")

    async def _reconnection_loop(self):
        """Continuous loop to attempt reconnection."""
        while not self.is_connected and not self._stop_reconnect:
            if await self.connect():
                break
            await asyncio.sleep(self.retry_delay)
