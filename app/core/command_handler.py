# app/core/command_handler.py

import asyncio
from typing import Dict, Any, List
from datetime import datetime
import logging

from app.api.models import AlarmNotification, AlarmSeverity, MachineCommand
from .clients.opcua_client import OPCUAClient


class CommandHandler:
    def __init__(self, opcua_client: OPCUAClient):
        self.opcua_client = opcua_client
        self.logger = logging.getLogger(__name__)
        self.active_alarms: Dict[str, AlarmNotification] = {}

    async def execute_command(self, command: MachineCommand, params: Dict[str, Any] = None) -> bool:
        try:
            if not isinstance(command, MachineCommand):
                try:
                    command = MachineCommand(command)
                except ValueError:
                    self.logger.error(f"Invalid command: {command}")
                    return False

            self.logger.info(f"Executing command: {command.value} with params: {params}")

            # Verifica allarmi attivi
            if command != MachineCommand.ACKNOWLEDGE_ALARM and self.active_alarms:
                self.logger.warning("Cannot execute command while alarms are active")
                return False

            # Esegui il comando
            if command == MachineCommand.START:
                return await self._start_machine(params)
            elif command == MachineCommand.STOP:
                return await self._stop_machine()
            elif command == MachineCommand.EMERGENCY_STOP:
                return await self._emergency_stop()
            else:
                self.logger.warning(f"Unhandled command: {command}")
                return False

        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            return False

    async def monitor_alarms(self):
        # Implement alarm monitoring logic
        pass

    def get_active_alarms(self) -> List[AlarmNotification]:
        return list(self.active_alarms.values())

    async def acknowledge_alarm(self, alarm_code: str) -> bool:
        if alarm_code in self.active_alarms:
            self.active_alarms[alarm_code].acknowledged = True
            return True
        return False
