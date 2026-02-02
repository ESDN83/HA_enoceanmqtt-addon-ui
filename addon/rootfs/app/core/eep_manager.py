"""
EEP Manager - Handles EnOcean Equipment Profile loading and parsing
Supports official EEP.xml and custom overrides

The EEP.xml is bundled with the addon - no external downloads required.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from lxml import etree
import yaml
import aiofiles

logger = logging.getLogger(__name__)


class EEPProfile:
    """Represents a single EEP profile"""

    def __init__(self, rorg: str, func: str, type_: str, description: str = ""):
        self.rorg = rorg
        self.func = func
        self.type = type_
        self.description = description
        self.fields: List[Dict[str, Any]] = []
        self.is_custom = False

    @property
    def eep_id(self) -> str:
        """Returns EEP identifier like A5-02-05"""
        return f"{self.rorg}-{self.func}-{self.type}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rorg": self.rorg,
            "func": self.func,
            "type": self.type,
            "eep_id": self.eep_id,
            "description": self.description,
            "fields": self.fields,
            "is_custom": self.is_custom
        }


class EEPManager:
    """Manages EEP profiles from official XML and custom overrides"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.custom_eep_path = os.path.join(config_path, "custom_eep")
        self.profiles: Dict[str, EEPProfile] = {}
        self._xml_root = None

    @property
    def profile_count(self) -> int:
        """Returns number of loaded profiles"""
        return len(self.profiles)

    async def initialize(self):
        """Initialize EEP manager - load base and custom profiles"""
        # Load base EEP.xml
        await self._load_base_eep()

        # Load custom overrides
        await self._load_custom_profiles()

        logger.info(f"EEP Manager initialized with {self.profile_count} profiles")

    async def _load_base_eep(self):
        """Load and parse the base EEP.xml file

        The EEP.xml is bundled with the addon in the data directory.
        Users can also provide their own EEP.xml in the config directory.
        No external downloads are performed.
        """
        # Bundled EEP.xml (shipped with addon)
        bundled_eep = os.path.join(os.path.dirname(__file__), "..", "data", "EEP.xml")
        # User-provided EEP.xml (optional override in config)
        user_eep = os.path.join(self.config_path, "EEP.xml")

        xml_content = None

        # Try user-provided EEP.xml first (allows updates without addon rebuild)
        if os.path.exists(user_eep):
            logger.info(f"Loading user EEP.xml from: {user_eep}")
            async with aiofiles.open(user_eep, 'rb') as f:
                xml_content = await f.read()

        # Use bundled version (default)
        elif os.path.exists(bundled_eep):
            logger.info(f"Loading bundled EEP.xml: {bundled_eep}")
            async with aiofiles.open(bundled_eep, 'rb') as f:
                xml_content = await f.read()

        else:
            logger.error(f"CRITICAL: Bundled EEP.xml not found at {bundled_eep}")

        if xml_content:
            await self._parse_eep_xml(xml_content)
        else:
            logger.warning("No EEP.xml found - using built-in minimal profiles")
            self._load_minimal_profiles()

    async def _parse_eep_xml(self, xml_content: bytes):
        """Parse EEP.xml content and extract profiles"""
        try:
            self._xml_root = etree.fromstring(xml_content)

            # Navigate the EEP.xml structure
            # Structure: telegrams -> telegram (rorg) -> profiles (func) -> profile (type)
            for telegram in self._xml_root.findall(".//telegram"):
                rorg = telegram.get("rorg", "")
                rorg_type = telegram.get("type", "")

                for profiles in telegram.findall("profiles"):
                    func = profiles.get("func", "")
                    func_desc = profiles.get("description", "")

                    for profile in profiles.findall("profile"):
                        type_ = profile.get("type", "")
                        type_desc = profile.get("description", func_desc)

                        # Format RORG, FUNC, TYPE as hex strings like "A5", "02", "05"
                        rorg_fmt = rorg.replace("0x", "").upper() if rorg.startswith("0x") else rorg.upper()
                        func_fmt = func.replace("0x", "").upper().zfill(2) if func else "00"
                        type_fmt = type_.replace("0x", "").upper().zfill(2) if type_ else "00"

                        eep_profile = EEPProfile(rorg_fmt, func_fmt, type_fmt, type_desc)

                        # Parse data fields
                        eep_profile.fields = self._parse_profile_fields(profile)

                        self.profiles[eep_profile.eep_id] = eep_profile

            logger.info(f"Parsed {len(self.profiles)} profiles from EEP.xml")

        except Exception as e:
            logger.error(f"Failed to parse EEP.xml: {e}")

    def _parse_profile_fields(self, profile_element) -> List[Dict[str, Any]]:
        """Parse data fields from a profile element"""
        fields = []

        data_element = profile_element.find("data")
        if data_element is None:
            return fields

        # Parse different field types
        for field in data_element:
            field_info = {
                "shortcut": field.get("shortcut", ""),
                "description": field.get("description", ""),
                "offset": int(field.get("offset", 0)),
                "size": int(field.get("size", 1)),
                "type": field.tag  # enum, value, status, etc.
            }

            # Parse enum values
            if field.tag == "enum":
                field_info["values"] = []
                for item in field.findall("item"):
                    field_info["values"].append({
                        "value": item.get("value", ""),
                        "description": item.get("description", "")
                    })

            # Parse value ranges
            elif field.tag == "value":
                field_info["unit"] = field.get("unit", "")
                range_elem = field.find("range")
                if range_elem is not None:
                    field_info["min"] = float(range_elem.get("min", 0))
                    field_info["max"] = float(range_elem.get("max", 255))
                scale_elem = field.find("scale")
                if scale_elem is not None:
                    field_info["scale_min"] = float(scale_elem.get("min", 0))
                    field_info["scale_max"] = float(scale_elem.get("max", 255))

            fields.append(field_info)

        return fields

    def _load_minimal_profiles(self):
        """Load minimal built-in profiles as fallback"""
        # Basic profiles for common devices
        minimal = [
            ("A5", "02", "05", "Temperature Sensor 0°C to +40°C"),
            ("A5", "04", "01", "Temperature and Humidity Sensor"),
            ("A5", "07", "01", "Occupancy Sensor"),
            ("A5", "30", "03", "Digital Input (4 channels)"),
            ("D5", "00", "01", "Single Input Contact"),
            ("F6", "02", "01", "Rocker Switch, 2 Rockers"),
            ("D2", "01", "0F", "Electronic Switch"),
            ("D2", "05", "00", "Blinds Control"),
        ]

        for rorg, func, type_, desc in minimal:
            profile = EEPProfile(rorg, func, type_, desc)
            self.profiles[profile.eep_id] = profile

    async def _load_custom_profiles(self):
        """Load custom EEP profile overrides"""
        if not os.path.exists(self.custom_eep_path):
            os.makedirs(self.custom_eep_path, exist_ok=True)
            return

        for filename in os.listdir(self.custom_eep_path):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.custom_eep_path, filename)
                try:
                    async with aiofiles.open(filepath, 'r') as f:
                        content = await f.read()
                        data = yaml.safe_load(content)

                        if data and "profile" in data:
                            profile_data = data["profile"]
                            rorg = profile_data.get("rorg", "").upper()
                            func = profile_data.get("func", "").upper().zfill(2)
                            type_ = profile_data.get("type", "").upper().zfill(2)
                            desc = profile_data.get("description", "Custom Profile")

                            profile = EEPProfile(rorg, func, type_, desc)
                            profile.fields = profile_data.get("fields", [])
                            profile.is_custom = True

                            self.profiles[profile.eep_id] = profile
                            logger.info(f"Loaded custom profile: {profile.eep_id}")

                except Exception as e:
                    logger.error(f"Failed to load custom profile {filename}: {e}")

    def get_profile(self, eep_id: str) -> Optional[EEPProfile]:
        """Get a profile by EEP ID"""
        return self.profiles.get(eep_id.upper())

    def get_profile_by_rorg_func_type(self, rorg: str, func: str, type_: str) -> Optional[EEPProfile]:
        """Get a profile by RORG, FUNC, TYPE"""
        eep_id = f"{rorg.upper()}-{func.upper().zfill(2)}-{type_.upper().zfill(2)}"
        return self.profiles.get(eep_id)

    def search_profiles(self, query: str) -> List[EEPProfile]:
        """Search profiles by description or EEP ID"""
        query = query.lower()
        results = []
        for profile in self.profiles.values():
            if query in profile.eep_id.lower() or query in profile.description.lower():
                results.append(profile)
        return results

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all profiles as dictionaries"""
        return [p.to_dict() for p in self.profiles.values()]

    def get_profiles_by_rorg(self, rorg: str) -> List[EEPProfile]:
        """Get all profiles for a specific RORG"""
        rorg = rorg.upper()
        return [p for p in self.profiles.values() if p.rorg == rorg]

    async def save_custom_profile(self, profile_data: Dict[str, Any]) -> bool:
        """Save a custom profile"""
        try:
            rorg = profile_data.get("rorg", "").upper()
            func = profile_data.get("func", "").upper().zfill(2)
            type_ = profile_data.get("type", "").upper().zfill(2)

            filename = f"{rorg}-{func}-{type_}.yaml"
            filepath = os.path.join(self.custom_eep_path, filename)

            os.makedirs(self.custom_eep_path, exist_ok=True)

            async with aiofiles.open(filepath, 'w') as f:
                await f.write(yaml.dump({"profile": profile_data}, default_flow_style=False))

            # Reload the profile
            profile = EEPProfile(rorg, func, type_, profile_data.get("description", ""))
            profile.fields = profile_data.get("fields", [])
            profile.is_custom = True
            self.profiles[profile.eep_id] = profile

            logger.info(f"Saved custom profile: {profile.eep_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save custom profile: {e}")
            return False

    async def delete_custom_profile(self, eep_id: str) -> bool:
        """Delete a custom profile"""
        try:
            profile = self.profiles.get(eep_id.upper())
            if not profile or not profile.is_custom:
                return False

            filename = f"{eep_id.upper()}.yaml"
            filepath = os.path.join(self.custom_eep_path, filename)

            if os.path.exists(filepath):
                os.remove(filepath)

            del self.profiles[eep_id.upper()]
            logger.info(f"Deleted custom profile: {eep_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete custom profile: {e}")
            return False
