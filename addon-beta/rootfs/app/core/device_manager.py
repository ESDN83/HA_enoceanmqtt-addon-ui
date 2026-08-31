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
    actuator_type: str = ""  # "light", "switch", "cover", or "" for sensor-only
    channel: int = 0  # I/O channel for multi-channel actuators (D2-01-11/12)
    invert: bool = False  # Cover only: reverse Open/Close + position direction
    # Cover only: full travel time in seconds. Eltako shutter actuators report
    # the time they actually ran, which only becomes a position when it is
    # measured against the full travel. 0 = not configured: the cover still
    # reports open/closed from the end-position confirmations, just no
    # percentage. See ADR-0014.
    travel_time: int = 0
    # Minutes of silence after which the device is reported unavailable to Home
    # Assistant. 0 means never, which is the old behaviour and the default: a
    # switch actuator only transmits when it is switched, so a watchdog would
    # declare a perfectly healthy one dead. See issue #37 and ADR-0011.
    availability_timeout: int = 0

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
            manufacturer=data.get("manufacturer", ""),
            actuator_type=data.get("actuator_type", ""),
            invert=bool(data.get("invert", False)),
            travel_time=int(data.get("travel_time", 0) or 0),
            channel=int(data.get("channel", 0) or 0),
            availability_timeout=int(data.get("availability_timeout", 0) or 0)
        )


class DeviceManager:
    """Manages device configurations"""

    def __init__(self, config_path: str, eep_manager=None):
        self.config_path = config_path
        self.eep_manager = eep_manager
        self.devices: Dict[str, Device] = {}
        self.devices_file = os.path.join(config_path, "devices.yaml")
        self.legacy_json_file = os.path.join(config_path, "devices.json")
        self.legacy_devices_file = os.path.join(config_path, "enoceanmqtt.devices")
        # One address can hold several devices, a 2-channel actuator is
        # configured once per output, all sharing the module address (#24).
        self._address_map: Dict[str, List[str]] = {}  # address -> [device_name]
        # Applied one-time data migrations, by id. Kept beside the devices
        # rather than inside devices.yaml, whose keys are device names.
        self.migrations_file = os.path.join(config_path, "migrations.yaml")

    @property
    def device_count(self) -> int:
        """Returns number of configured devices"""
        return len(self.devices)

    def _rebuild_address_map(self):
        """Rebuild address lookup map from current devices"""
        self._address_map = {}
        for name, device in self.devices.items():
            norm = device.address.strip().upper().replace("0X", "")
            if norm:
                self._address_map.setdefault(norm, []).append(name)

    async def load_devices(self):
        """Load devices from configuration file"""
        # Try YAML format first (current format)
        if os.path.exists(self.devices_file):
            await self._load_yaml_devices()
        # Migrate from JSON format (legacy)
        elif os.path.exists(self.legacy_json_file):
            await self._load_json_devices()
            await self.save_devices()
            logger.info("Migrated devices.json -> devices.yaml")
        # Fallback to INI format (legacy ChristopheHD format)
        elif os.path.exists(self.legacy_devices_file):
            await self._load_ini_devices()
        else:
            logger.info("No device configuration found - starting fresh")
        self._rebuild_address_map()
        await self._apply_migrations()

    # Up used to be the bottom half of the rocker on an F6 cover and down the
    # top one, the wrong way round for an Eltako directional pushbutton. 1.8.1
    # swapped them. An update must not reverse a shutter that someone has been
    # using for months, so every cover that exists at the moment of the update
    # is pinned to the behaviour it had, by ticking "Reverse direction" for it:
    # the flag was ignored on this path before, so its old value says nothing,
    # and setting it reproduces the old telegrams exactly. Devices added after
    # the update get the correct direction without the flag. See ADR-0014.
    COVER_DIRECTION_MIGRATION = "cover-rocker-direction-1.8.1"

    async def _applied_migrations(self) -> List[str]:
        if not os.path.exists(self.migrations_file):
            return []
        try:
            async with aiofiles.open(self.migrations_file, 'r') as f:
                data = yaml.safe_load(await f.read()) or {}
            return list(data.get("applied", []))
        except Exception as e:
            logger.error(f"Failed to read {self.migrations_file}: {e}")
            # Unreadable is not "never applied": re-running a migration on a
            # live installation is worse than skipping it.
            return [self.COVER_DIRECTION_MIGRATION]

    async def _mark_migration(self, applied: List[str], migration: str):
        applied = list(applied) + [migration]
        try:
            async with aiofiles.open(self.migrations_file, 'w') as f:
                await f.write(yaml.dump({"applied": applied}, default_flow_style=False))
        except Exception as e:
            logger.error(f"Failed to record migration {migration}: {e}")

    async def _apply_migrations(self):
        """Run one-time data migrations, at most once per installation."""
        applied = await self._applied_migrations()
        if self.COVER_DIRECTION_MIGRATION in applied:
            return

        pinned = []
        for device in self.devices.values():
            # D2-05 blinds speak structured commands and were never affected.
            if device.actuator_type != "cover":
                continue
            if device.rorg.upper() == "D2" and str(device.func).zfill(2) == "05":
                continue
            if not device.invert:
                device.invert = True
                pinned.append(device.name)

        if pinned:
            await self.save_devices()
            logger.info(
                "Direction migration: 'Reverse direction' was set on "
                f"{', '.join(pinned)} so the update does not swap open and "
                "close on covers that already worked. Untick it if the shutter "
                "runs the wrong way."
            )
        await self._mark_migration(applied, self.COVER_DIRECTION_MIGRATION)

    async def _load_yaml_devices(self):
        """Load devices from YAML file"""
        try:
            async with aiofiles.open(self.devices_file, 'r') as f:
                content = await f.read()
                data = yaml.safe_load(content) or {}

                for name, device_data in data.items():
                    self.devices[name] = Device.from_dict(name, device_data)

            logger.info(f"Loaded {len(self.devices)} devices from YAML")

        except Exception as e:
            logger.error(f"Failed to load devices from YAML: {e}")

    async def _load_json_devices(self):
        """Load devices from JSON file (legacy)"""
        try:
            async with aiofiles.open(self.legacy_json_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)

                for name, device_data in data.items():
                    self.devices[name] = Device.from_dict(name, device_data)

            logger.info(f"Loaded {len(self.devices)} devices from JSON (legacy)")

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

                # Read sender (ChristopheHD uses "sender", we also support "sender_id" for backward compat)
                sender = config.get(section, "sender", fallback="")
                if not sender:
                    sender = config.get(section, "sender_id", fallback="")

                device_data = {
                    "address": config.get(section, "address", fallback=""),
                    "rorg": self._format_hex(config.get(section, "rorg", fallback="")),
                    "func": self._format_hex(config.get(section, "func", fallback="")),
                    "type": self._format_hex(config.get(section, "type", fallback="")),
                    "sender_id": sender,
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

            # Save as YAML (current format)
            data = {name: device.to_dict() for name, device in self.devices.items()}

            async with aiofiles.open(self.devices_file, 'w') as f:
                await f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True))

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
                    lines.append(f"sender = {device.sender_id}")
                lines.append("")

            async with aiofiles.open(self.legacy_devices_file, 'w') as f:
                await f.write("\n".join(lines))

        except Exception as e:
            logger.error(f"Failed to save INI devices: {e}")

    def get_device(self, name: str) -> Optional[Device]:
        """Get device by name"""
        return self.devices.get(name)

    def get_device_by_address(self, address: str) -> Optional[Device]:
        """Get the first device registered for an address (O(1) lookup)."""
        devices = self.get_devices_by_address(address)
        return devices[0] if devices else None

    def get_devices_by_address(self, address: str) -> List[Device]:
        """Get ALL devices registered for an address.

        A 2-channel actuator is configured as one device per output, all with
        the same module address, every one of them has to receive the state
        of an incoming telegram, otherwise the second channel stays dead (#24).
        """
        norm_addr = address.strip().upper().replace("0X", "")
        names = self._address_map.get(norm_addr) or []
        return [self.devices[n] for n in names if n in self.devices]

    async def add_device(self, device: Device) -> bool:
        """Add a new device"""
        if device.name in self.devices:
            logger.warning(f"Device {device.name} already exists")
            return False

        self.devices[device.name] = device
        self._rebuild_address_map()
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

        self._rebuild_address_map()
        await self.save_devices()
        logger.info(f"Updated device: {name}")
        return True

    async def rename_device(self, old_name: str, new_name: str) -> bool:
        """Rename a device (re-key). The name is the primary key and the MQTT
        topic base, so this moves the entry and updates the device's name.
        Returns False if the source is missing or the target already exists."""
        new_name = (new_name or "").strip()
        if not new_name or old_name not in self.devices or new_name in self.devices:
            return False
        device = self.devices.pop(old_name)
        device.name = new_name
        self.devices[new_name] = device
        self._rebuild_address_map()
        await self.save_devices()
        logger.info(f"Renamed device: {old_name} -> {new_name}")
        return True

    async def delete_device(self, name: str) -> bool:
        """Delete a device"""
        if name not in self.devices:
            return False

        del self.devices[name]
        self._rebuild_address_map()
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
