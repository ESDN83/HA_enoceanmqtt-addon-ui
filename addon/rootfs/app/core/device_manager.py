"""
Device Manager - Handles device configuration storage and management
"""

import os
import logging
import configparser
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
import aiofiles
import yaml
import json

logger = logging.getLogger(__name__)


@dataclass
class Device:
    """Represents an EnOcean device"""
    name: str
    address: str  # Hex address like 0x05834FA4
    rorg: str     # Radio organization e.g., A5, F6, D5, D2
    func: str     # Function e.g., 02
    type: str     # Type e.g., 05
    sender_id: str = ""  # For bidirectional devices
    description: str = ""
    room: str = ""
    manufacturer: str = ""

    @property
    def eep_id(self) -> str:
        """Returns EEP identifier like A5-02-05"""
        return f"{self.rorg}-{self.func}-{self.type}"

    @property
    def address_int(self) -> int:
        """Returns address as integer"""
        if self.address.startswith("0x"):
            return int(self.address, 16)
        return int(self.address)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "Device":
        """Create from dictionary"""
        return cls(
            name=name,
            address=data.get("address", ""),
            rorg=data.get("rorg", ""),
            func=data.get("func", ""),
            type=data.get("type", ""),
            sender_id=data.get("sender_id", ""),
            description=data.get("description", ""),
            room=data.get("room", ""),
            manufacturer=data.get("manufacturer", "")
        )


class DeviceManager:
    """Manages device configurations"""

    def __init__(self, config_path: str, eep_manager=None):
        self.config_path = config_path
        self.eep_manager = eep_manager
        self.devices: Dict[str, Device] = {}
        self.devices_file = os.path.join(config_path, "devices.json")
        self.legacy_devices_file = os.path.join(config_path, "enoceanmqtt.devices")

    @property
    def device_count(self) -> int:
        """Returns number of configured devices"""
        return len(self.devices)

    async def load_devices(self):
        """Load devices from configuration file"""
        # Try JSON format first (new format)
        if os.path.exists(self.devices_file):
            await self._load_json_devices()
        # Fallback to INI format (legacy ChristopheHD format)
        elif os.path.exists(self.legacy_devices_file):
            await self._load_ini_devices()
        else:
            logger.info("No device configuration found - starting fresh")

    async def _load_json_devices(self):
        """Load devices from JSON file"""
        try:
            async with aiofiles.open(self.devices_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)

                for name, device_data in data.items():
                    self.devices[name] = Device.from_dict(name, device_data)

            logger.info(f"Loaded {len(self.devices)} devices from JSON")

        except Exception as e:
            logger.error(f"Failed to load devices from JSON: {e}")

    async def _load_ini_devices(self):
        """Load devices from INI file (ChristopheHD format)"""
        try:
            config = configparser.ConfigParser()
            config.read(self.legacy_devices_file)

            for section in config.sections():
                if section == "CONFIG":
                    continue

                device_data = {
                    "address": config.get(section, "address", fallback=""),
                    "rorg": self._format_hex(config.get(section, "rorg", fallback="")),
                    "func": self._format_hex(config.get(section, "func", fallback="")),
                    "type": self._format_hex(config.get(section, "type", fallback="")),
                    "sender_id": config.get(section, "sender_id", fallback=""),
                }

                self.devices[section] = Device.from_dict(section, device_data)

            logger.info(f"Loaded {len(self.devices)} devices from INI (legacy format)")

            # Migrate to new format
            await self.save_devices()

        except Exception as e:
            logger.error(f"Failed to load devices from INI: {e}")

    def _format_hex(self, value: str) -> str:
        """Format hex value consistently (e.g., 0xA5 -> A5)"""
        if not value:
            return ""
        value = value.strip()
        if value.startswith("0x"):
            return value[2:].upper()
        return value.upper()

    async def save_devices(self):
        """Save devices to configuration file"""
        try:
            os.makedirs(self.config_path, exist_ok=True)

            # Save as JSON (new format)
            data = {name: device.to_dict() for name, device in self.devices.items()}

            async with aiofiles.open(self.devices_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))

            # Also save as INI for compatibility with enocean-mqtt
            await self._save_ini_devices()

            logger.info(f"Saved {len(self.devices)} devices")

        except Exception as e:
            logger.error(f"Failed to save devices: {e}")
            raise

    async def _save_ini_devices(self):
        """Save devices in INI format for enocean-mqtt compatibility"""
        try:
            lines = []
            for name, device in self.devices.items():
                lines.append(f"[{name}]")
                lines.append(f"address = {device.address}")
                lines.append(f"rorg = 0x{device.rorg}")
                lines.append(f"func = 0x{device.func}")
                lines.append(f"type = 0x{device.type}")
                if device.sender_id:
                    lines.append(f"sender_id = {device.sender_id}")
                lines.append("")

            async with aiofiles.open(self.legacy_devices_file, 'w') as f:
                await f.write("\n".join(lines))

        except Exception as e:
            logger.error(f"Failed to save INI devices: {e}")

    def get_device(self, name: str) -> Optional[Device]:
        """Get device by name"""
        return self.devices.get(name)

    def get_device_by_address(self, address: str) -> Optional[Device]:
        """Get device by address"""
        # Normalize address format
        if not address.startswith("0x"):
            address = f"0x{address}"
        address = address.upper()

        for device in self.devices.values():
            dev_addr = device.address.upper()
            if not dev_addr.startswith("0x"):
                dev_addr = f"0x{dev_addr}"
            if dev_addr == address:
                return device
        return None

    async def add_device(self, device: Device) -> bool:
        """Add a new device"""
        if device.name in self.devices:
            logger.warning(f"Device {device.name} already exists")
            return False

        self.devices[device.name] = device
        await self.save_devices()
        logger.info(f"Added device: {device.name}")
        return True

    async def update_device(self, name: str, device_data: Dict[str, Any]) -> bool:
        """Update an existing device"""
        if name not in self.devices:
            return False

        device = self.devices[name]
        for key, value in device_data.items():
            if hasattr(device, key):
                setattr(device, key, value)

        await self.save_devices()
        logger.info(f"Updated device: {name}")
        return True

    async def delete_device(self, name: str) -> bool:
        """Delete a device"""
        if name not in self.devices:
            return False

        del self.devices[name]
        await self.save_devices()
        logger.info(f"Deleted device: {name}")
        return True

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Get all devices as dictionaries"""
        return [device.to_dict() for device in self.devices.values()]

    def search_devices(self, query: str) -> List[Device]:
        """Search devices by name or address"""
        query = query.lower()
        results = []
        for device in self.devices.values():
            if query in device.name.lower() or query in device.address.lower():
                results.append(device)
        return results
