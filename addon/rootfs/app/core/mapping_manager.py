"""
Mapping Manager - Handles EEP to MQTT/HA entity mappings

Generates Home Assistant MQTT discovery configurations compatible with
ChristopheHD/HA_enoceanmqtt-addon discovery format.

Discovery UID format: enocean_{EEP}_{ADDR}_{SHORTCUT}
  e.g., enocean_A53003_05834FA4_DI0
With sender: enocean_{EEP}_{ADDR}_{SENDER}_{SHORTCUT}
  e.g., enocean_A53003_05834FA4_AABBCCDD_DI0
"""

import os
import logging
from typing import Dict, List, Optional, Any
import yaml
import aiofiles

logger = logging.getLogger(__name__)

# Default mappings for common EEP profiles
DEFAULT_MAPPINGS = {
    # 4BS Temperature Sensors (A5-02-xx)
    "A5-02-05": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "value_template": "{{ value_json.TMP }}"
        }
    },
    # 4BS Temperature and Humidity (A5-04-01)
    "A5-04-01": {
        "TMP": {
            "component": "sensor",
            "name": "Temperature",
            "device_class": "temperature",
            "unit_of_measurement": "°C"
        },
        "HUM": {
            "component": "sensor",
            "name": "Humidity",
            "device_class": "humidity",
            "unit_of_measurement": "%"
        }
    },
    # 4BS Occupancy Sensor (A5-07-01)
    "A5-07-01": {
        "PIR": {
            "component": "binary_sensor",
            "name": "Occupancy",
            "device_class": "occupancy"
        },
        "SVC": {
            "component": "sensor",
            "name": "Supply Voltage",
            "device_class": "voltage",
            "unit_of_measurement": "V"
        }
    },
    # 4BS Digital Input (A5-30-03)
    "A5-30-03": {
        "DI0": {
            "component": "binary_sensor",
            "name": "Input 0",
            "device_class": "power"
        },
        "DI1": {
            "component": "binary_sensor",
            "name": "Input 1",
            "device_class": "power"
        },
        "DI2": {
            "component": "binary_sensor",
            "name": "Input 2",
            "device_class": "power"
        },
        "DI3": {
            "component": "binary_sensor",
            "name": "Input 3",
            "device_class": "power"
        }
    },
    # 1BS Contact Sensor (D5-00-01)
    "D5-00-01": {
        "CO": {
            "component": "binary_sensor",
            "name": "Contact",
            "device_class": "door"
        }
    },
    # RPS Rocker Switch (F6-02-01)
    "F6-02-01": {
        "R1": {
            "component": "binary_sensor",
            "name": "Rocker 1",
            "device_class": "power"
        },
        "R2": {
            "component": "binary_sensor",
            "name": "Rocker 2",
            "device_class": "power"
        },
        "EB": {
            "component": "binary_sensor",
            "name": "Energy Bow",
            "device_class": "power"
        }
    },
    # VLD Electronic Switch (D2-01-0F)
    "D2-01-0F": {
        "CMD": {
            "component": "switch",
            "name": "Switch",
            "icon": "mdi:power"
        },
        "OV": {
            "component": "sensor",
            "name": "Output Value",
            "unit_of_measurement": "%"
        }
    },
    # VLD Blinds Control (D2-05-00)
    "D2-05-00": {
        "POS": {
            "component": "cover",
            "name": "Position",
            "device_class": "blind"
        },
        "ANG": {
            "component": "sensor",
            "name": "Angle",
            "unit_of_measurement": "°"
        }
    }
}


def _normalize_address(address: str) -> str:
    """Normalize address to 8-char uppercase hex without 0x prefix.
    e.g., '0x05834FA4' -> '05834FA4'
    """
    addr = address.strip().upper()
    if addr.startswith("0X"):
        addr = addr[2:]
    return addr.zfill(8)


def _normalize_eep(eep_id: str) -> str:
    """Normalize EEP to 6-char format without dashes.
    e.g., 'A5-30-03' -> 'A53003'
    """
    return eep_id.upper().replace("-", "")


class MappingManager:
    """Manages EEP to MQTT/HA entity mappings"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.mappings_file = os.path.join(config_path, "mapping.yaml")
        self.custom_mappings: Dict[str, Dict[str, Any]] = {}

    async def initialize(self):
        """Initialize mapping manager - load custom mappings"""
        await self._load_custom_mappings()
        logger.info(f"Mapping Manager initialized with {len(self.custom_mappings)} custom mappings")

    async def _load_custom_mappings(self):
        """Load custom mappings from file"""
        if not os.path.exists(self.mappings_file):
            return

        try:
            async with aiofiles.open(self.mappings_file, 'r') as f:
                content = await f.read()
                data = yaml.safe_load(content)
                if data and isinstance(data, dict):
                    self.custom_mappings = data
                    logger.info(f"Loaded {len(self.custom_mappings)} custom mappings")
        except Exception as e:
            logger.error(f"Failed to load custom mappings: {e}")

    async def save_mappings(self):
        """Save custom mappings to file"""
        try:
            os.makedirs(self.config_path, exist_ok=True)
            async with aiofiles.open(self.mappings_file, 'w') as f:
                await f.write(yaml.dump(
                    self.custom_mappings,
                    default_flow_style=False,
                    allow_unicode=True
                ))
            logger.info("Saved custom mappings")
        except Exception as e:
            logger.error(f"Failed to save mappings: {e}")

    def get_mapping(self, eep_id: str) -> Dict[str, Any]:
        """Get mapping for an EEP profile

        Priority:
        1. Custom mapping
        2. Default mapping
        3. Empty dict
        """
        eep_id = eep_id.upper()

        if eep_id in self.custom_mappings:
            return self.custom_mappings[eep_id]

        if eep_id in DEFAULT_MAPPINGS:
            return DEFAULT_MAPPINGS[eep_id]

        return {}

    async def set_mapping(self, eep_id: str, mapping: Dict[str, Any]):
        """Set custom mapping for an EEP profile"""
        eep_id = eep_id.upper()
        self.custom_mappings[eep_id] = mapping
        await self.save_mappings()
        logger.info(f"Set mapping for {eep_id}")

    async def delete_mapping(self, eep_id: str) -> bool:
        """Delete custom mapping for an EEP profile"""
        eep_id = eep_id.upper()
        if eep_id in self.custom_mappings:
            del self.custom_mappings[eep_id]
            await self.save_mappings()
            logger.info(f"Deleted mapping for {eep_id}")
            return True
        return False

    def get_all_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get all mappings (merged default + custom)"""
        result = dict(DEFAULT_MAPPINGS)
        result.update(self.custom_mappings)
        return result

    def build_unique_id(self, eep_id: str, address: str, sender: str, shortcut: str) -> str:
        """Build ChristopheHD-compatible unique ID for HA discovery.

        Format: enocean_{EEP6}_{ADDR8}_{SHORTCUT}
        With sender: enocean_{EEP6}_{ADDR8}_{SENDER8}_{SHORTCUT}
        """
        eep = _normalize_eep(eep_id)
        addr = _normalize_address(address)

        if sender:
            sndr = _normalize_address(sender)
            return f"enocean_{eep}_{addr}_{sndr}_{shortcut}"
        else:
            return f"enocean_{eep}_{addr}_{shortcut}"

    def get_ha_discovery_configs(
        self,
        device_name: str,
        eep_id: str,
        device_address: str,
        device_sender: str,
        mqtt_prefix: str,
        device_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate Home Assistant MQTT discovery configurations.

        Returns a list of discovery configs for all entities defined in the mapping.
        Uses ChristopheHD-compatible UID format and per-device availability.
        """
        mapping = self.get_mapping(eep_id)
        configs = []

        for field_name, field_config in mapping.items():
            component = field_config.get("component", "sensor")

            # Build unique ID (ChristopheHD compatible)
            unique_id = self.build_unique_id(eep_id, device_address, device_sender, field_name)

            # Build discovery config
            config = {
                "name": field_config.get("name", field_name),
                "unique_id": unique_id,
                "object_id": f"{device_name}_{field_name}".lower().replace(" ", "_"),
                "state_topic": f"{mqtt_prefix}/{device_name}/state",
                "value_template": field_config.get(
                    "value_template",
                    f"{{{{ value_json.{field_name} }}}}"
                )
            }

            # Add optional fields
            if "device_class" in field_config:
                config["device_class"] = field_config["device_class"]
            if "unit_of_measurement" in field_config:
                config["unit_of_measurement"] = field_config["unit_of_measurement"]
            if "icon" in field_config:
                config["icon"] = field_config["icon"]

            # Add device info
            config["device"] = device_info

            # Add command topic for controllable entities
            if component in ["switch", "light", "cover", "climate", "fan"]:
                config["command_topic"] = f"{mqtt_prefix}/{device_name}/set"

                if component == "cover":
                    config["position_topic"] = f"{mqtt_prefix}/{device_name}/state"
                    config["position_template"] = f"{{{{ value_json.{field_name} }}}}"
                    config["set_position_topic"] = f"{mqtt_prefix}/{device_name}/position/set"

            # Per-device availability (not global gateway status)
            config["availability"] = {
                "topic": f"{mqtt_prefix}/{device_name}/availability",
                "payload_available": "online",
                "payload_not_available": "offline"
            }

            configs.append({
                "component": component,
                "unique_id": unique_id,
                "config": config
            })

        return configs

    def build_device_info(self, device) -> Dict[str, Any]:
        """Build HA device info from device object"""
        addr = _normalize_address(device.address)
        return {
            "identifiers": [f"enocean_{addr}"],
            "name": device.description or device.name,
            "manufacturer": device.manufacturer or "EnOcean",
            "model": device.eep_id,
        }
