from typing import Dict, List, Optional, Deque
from datetime import datetime, timedelta
import statistics
from dataclasses import dataclass
from collections import deque

@dataclass
class ProcessedMetrics:
    """Container for processed metrics"""
    average_consumption: float
    average_cutting_speed: float
    efficiency_rate: float
    pieces_per_hour: float
    total_pieces: int
    uptime_percentage: float
    active_time: timedelta

class DataProcessor:
    def __init__(self, window_size: int = 3600):  # Default 1 hour window
        """
        Initialize the data processor with a sliding window for metrics
        
        Args:
            window_size (int): Size of the sliding window in seconds
        """
        self.window_size = window_size
        self.consumption_history: Deque[tuple[datetime, float]] = deque()
        self.speed_history: Deque[tuple[datetime, float]] = deque()
        self.pieces_history: Deque[tuple[datetime, int]] = deque()
        self.start_time = datetime.now()
        self.total_downtime = timedelta()
        self.last_active_timestamp = datetime.now()
        
        # Current state tracking
        self.current_consumption = 0.0
        self.current_speed = 0.0
        self.current_pieces = 0
        self.current_active = False
        self.current_timestamp = datetime.now()

    def update_power_consumption(self, value: float):
        """Update power consumption value and recalculate metrics"""
        self.current_consumption = float(value)
        self.update_metrics(
            datetime.now(),
            self.current_consumption,
            self.current_speed,
            self.current_pieces,
            self.current_active
        )

    def update_cutting_speed(self, value: float):
        """Update cutting speed value and recalculate metrics"""
        self.current_speed = float(value)
        self.update_metrics(
            datetime.now(),
            self.current_consumption,
            self.current_speed,
            self.current_pieces,
            self.current_active
        )

    def update_pieces_count(self, value: int):
        """Update pieces count and recalculate metrics"""
        self.current_pieces = int(value)
        self.update_metrics(
            datetime.now(),
            self.current_consumption,
            self.current_speed,
            self.current_pieces,
            self.current_active
        )

    def update_active_status(self, value: bool):
        """Update active status and recalculate metrics"""
        self.current_active = bool(value)
        self.current_timestamp = datetime.now()
        self.update_metrics(
            self.current_timestamp,
            self.current_consumption,
            self.current_speed,
            self.current_pieces,
            self.current_active
        )

    def _cleanup_old_data(self, current_time: datetime):
        """Remove data points older than window_size seconds"""
        threshold = current_time - timedelta(seconds=self.window_size)
        
        for history in [self.consumption_history, self.speed_history, self.pieces_history]:
            while history and history[0][0] < threshold:
                history.popleft()

    def update_metrics(self, timestamp: datetime, consumption: float, 
                      cutting_speed: float, pieces: int, is_active: bool):
        """
        Update metrics with new data point
        
        Args:
            timestamp (datetime): Timestamp of the data point
            consumption (float): Current power consumption
            cutting_speed (float): Current cutting speed
            pieces (int): Current piece count
            is_active (bool): Whether the machine is currently active
        """
        self._cleanup_old_data(timestamp)
        
        self.consumption_history.append((timestamp, consumption))
        self.speed_history.append((timestamp, cutting_speed))
        self.pieces_history.append((timestamp, pieces))

        if not is_active and self.last_active_timestamp:
            self.total_downtime += timestamp - self.last_active_timestamp
        self.last_active_timestamp = timestamp if is_active else None

    def calculate_average_consumption(self, minutes: int) -> float:
        """Calculate average power consumption over last n minutes"""
        if not self.consumption_history:
            return 0.0
            
        threshold = datetime.now() - timedelta(minutes=minutes)
        recent_consumption = [c for t, c in self.consumption_history if t >= threshold]
        
        return statistics.mean(recent_consumption) if recent_consumption else 0.0

    def calculate_cutting_efficiency(self) -> float:
        """
        Calculate cutting efficiency based on pieces produced vs power consumed
        Returns efficiency rate (pieces per kWh)
        """
        if not self.consumption_history or not self.pieces_history:
            return 0.0
            
        total_consumption = sum(c for _, c in self.consumption_history) / 3600  # Convert to kWh
        if total_consumption == 0:
            return 0.0
            
        pieces_produced = self.pieces_history[-1][1] - self.pieces_history[0][1]
        return pieces_produced / total_consumption if total_consumption > 0 else 0.0

    def calculate_pieces_per_hour(self) -> float:
        """Calculate average pieces produced per hour"""
        if len(self.pieces_history) < 2:
            return 0.0
            
        time_diff = (self.pieces_history[-1][0] - self.pieces_history[0][0]).total_seconds() / 3600
        if time_diff == 0:
            return 0.0
            
        pieces_diff = self.pieces_history[-1][1] - self.pieces_history[0][1]
        return pieces_diff / time_diff

    def get_processed_metrics(self) -> ProcessedMetrics:
        """Get all processed metrics"""
        current_time = datetime.now()
        total_time = (current_time - self.start_time).total_seconds()
        uptime = total_time - self.total_downtime.total_seconds()
        
        return ProcessedMetrics(
            average_consumption=self.calculate_average_consumption(minutes=60),
            average_cutting_speed=statistics.mean([s for _, s in self.speed_history]) if self.speed_history else 0.0,
            efficiency_rate=self.calculate_cutting_efficiency(),
            pieces_per_hour=self.calculate_pieces_per_hour(),
            total_pieces=self.pieces_history[-1][1] if self.pieces_history else 0,
            uptime_percentage=(uptime / total_time * 100) if total_time > 0 else 0.0,
            active_time=timedelta(seconds=uptime)
        )

    def reset(self):
        """Reset all metrics"""
        self.consumption_history.clear()
        self.speed_history.clear()
        self.pieces_history.clear()
        self.start_time = datetime.now()
        self.total_downtime = timedelta()
        self.last_active_timestamp = datetime.now()
        # Reset current values
        self.current_consumption = 0.0
        self.current_speed = 0.0
        self.current_pieces = 0
        self.current_active = False
        self.current_timestamp = datetime.now()