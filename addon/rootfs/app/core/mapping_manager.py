"""
Mapping Manager - Handles EEP to MQTT/HA entity mappings
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

        # Check custom mappings first
        if eep_id in self.custom_mappings:
            return self.custom_mappings[eep_id]

        # Fall back to default mappings
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

    def get_ha_discovery_configs(
        self,
        device_name: str,
        eep_id: str,
        device_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate Home Assistant MQTT discovery configurations

        Returns a list of discovery configs for all entities defined in the mapping
        """
        mapping = self.get_mapping(eep_id)
        configs = []

        for field_name, field_config in mapping.items():
            component = field_config.get("component", "sensor")

            # Build unique ID
            unique_id = f"enocean_{device_name}_{field_name}".lower().replace(" ", "_")

            # Build discovery config
            config = {
                "name": field_config.get("name", field_name),
                "unique_id": unique_id,
                "object_id": f"{device_name}_{field_name}".lower().replace(" ", "_"),
                "state_topic": f"enocean/{device_name}/state",
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
                config["command_topic"] = f"enocean/{device_name}/set"

                # Add component-specific fields
                if component == "light" and field_config.get("brightness"):
                    config["brightness_state_topic"] = f"enocean/{device_name}/state"
                    config["brightness_value_template"] = f"{{{{ value_json.{field_name} }}}}"
                    config["brightness_command_topic"] = f"enocean/{device_name}/brightness/set"
                    config["brightness_scale"] = 100

                if component == "cover":
                    config["position_topic"] = f"enocean/{device_name}/state"
                    config["position_template"] = f"{{{{ value_json.{field_name} }}}}"
                    config["set_position_topic"] = f"enocean/{device_name}/position/set"

            # Add availability
            config["availability"] = {
                "topic": "enocean/status",
                "payload_available": "online",
                "payload_not_available": "offline"
            }

            configs.append({
                "component": component,
                "config": config
            })

        return configs

    def build_device_info(self, device) -> Dict[str, Any]:
        """Build HA device info from device object"""
        return {
            "identifiers": [f"enocean_{device.address}"],
            "name": device.description or device.name,
            "manufacturer": device.manufacturer or "EnOcean",
            "model": device.eep_id,
            "via_device": "enocean_gateway"
        }
