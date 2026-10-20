"""
EEP Manager - Handles EnOcean Equipment Profile loading and parsing
Supports official EEP.xml and custom overrides

The EEP.xml is bundled with the addon - no external downloads required.
"""

import os
import json
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
        self.ha_mapping: Dict[str, Dict[str, Any]] = {}  # EEP field → HA entity mapping
        self.is_custom = False
        # Where the profile comes from (ADR-0027): "eep_xml", "bundled" (ships
        # with the app), "bundled_modified" (the user's edit of a bundled one)
        # or "custom" (the user's own).
        self.source = "eep_xml"
        # A bundled profile changed after the user edited their copy of it.
        self.bundled_newer = False

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
            "ha_mapping": self.ha_mapping,
            "is_custom": self.is_custom,
            "source": self.source,
            "bundled_newer": self.bundled_newer
        }


class EEPManager:
    """Manages EEP profiles from official XML and custom overrides"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.custom_eep_path = os.path.join(config_path, "custom_eep")
        self.profiles: Dict[str, EEPProfile] = {}
        self._xml_root = None
        self._override_cache: Dict[str, Any] = {}
        # Overlay model (ADR-0027): bundled profiles are read from the app
        # image and never copied to /data. A user file in /data overrides one,
        # a hidden mark removes it. EEP.xml stays underneath both.
        self.base_profiles: Dict[str, EEPProfile] = {}
        self.bundled: Dict[str, Dict[str, Any]] = {}
        self.user_data: Dict[str, Dict[str, Any]] = {}
        self.user_files: Dict[str, str] = {}  # eep_id -> file name in /data
        self.hidden_bundled: set = set()

    @property
    def profile_count(self) -> int:
        """Returns number of loaded profiles"""
        return len(self.profiles)

    def get_eep_info(self) -> Dict[str, Any]:
        """Get information about loaded EEP.xml"""
        user_eep = os.path.join(self.config_path, "EEP.xml")
        bundled_eep = os.path.join(os.path.dirname(__file__), "..", "data", "EEP.xml")
        user_exists = os.path.exists(user_eep)
        bundled_exists = os.path.exists(bundled_eep)

        if user_exists:
            source = "user"
        elif bundled_exists:
            source = "bundled"
        else:
            source = "minimal"

        return {
            "source": source,
            "profile_count": self.profile_count,
            "user_file_exists": user_exists,
            "user_file_size": os.path.getsize(user_eep) if user_exists else 0,
            "bundled_file_size": os.path.getsize(bundled_eep) if bundled_exists else 0,
        }

    async def initialize(self):
        """Initialize EEP manager - load base and custom profiles"""
        # Also runs again after a config restore: start from scratch, or the
        # previous custom profiles would be taken for EEP.xml ones below.
        self.profiles = {}
        # Load base EEP.xml
        await self._load_base_eep()

        self.base_profiles = dict(self.profiles)

        # Bundled profiles, the user's hidden marks, then the user's own files
        # (ADR-0027). Until beta11 bundled profiles were copied into /data and
        # overwritten on every start; _drop_seeded_copies retires those copies.
        await self._load_bundled_profiles()
        await self._load_hidden()
        await self._load_custom_profiles()
        await self._drop_seeded_copies()
        for eep_id in set(self.bundled) | set(self.user_data):
            self._apply(eep_id)

        # Load mapping overrides into sync cache (used by mapping_manager)
        await self._load_overrides()

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

        # Support multiple <data> elements (some profiles have data command="1", command="2", etc.)
        data_elements = profile_element.findall("data")
        if not data_elements:
            return fields

        for data_element in data_elements:
            # A bidirectional profile (A5-20-01, -04, -06 radiator valves) has
            # a direction="1" block for what the device sends and a
            # direction="2" block for what the gateway sends back. Only the
            # first describes a received telegram; merging both put the reply
            # fields over the real ones (direction 2's TMP replaced the
            # ambient temperature). The reply side is not decoded at all.
            if data_element.get("direction") == "2":
                continue

            # Track which command this data block belongs to
            command_id = data_element.get("command", None)

            # Parse different field types
            for field in data_element:
                field_info = {
                    "shortcut": field.get("shortcut", ""),
                    "description": field.get("description", ""),
                    "offset": int(field.get("offset", 0)),
                    "size": int(field.get("size", 1)),
                    "type": field.tag  # enum, value, status, command, etc.
                }

                # Tag with command ID if from a multi-command profile
                if command_id is not None:
                    field_info["command"] = command_id

                # Parse enum values
                if field.tag == "enum":
                    field_info["values"] = []
                    for item in field.findall("item"):
                        field_info["values"].append({
                            "value": item.get("value", ""),
                            "description": item.get("description", "")
                        })
                    # Also parse range items (e.g., "3-127: reserved")
                    for rangeitem in field.findall("rangeitem"):
                        field_info["values"].append({
                            "start": rangeitem.get("start", ""),
                            "end": rangeitem.get("end", ""),
                            "description": rangeitem.get("description", ""),
                            "type": "range"
                        })

                # Parse value ranges (child elements, not attributes!)
                elif field.tag == "value":
                    field_info["unit"] = field.get("unit", "")
                    range_elem = field.find("range")
                    if range_elem is not None:
                        min_el = range_elem.find("min")
                        max_el = range_elem.find("max")
                        field_info["min"] = float(min_el.text) if min_el is not None and min_el.text else 0
                        field_info["max"] = float(max_el.text) if max_el is not None and max_el.text else 255
                    scale_elem = field.find("scale")
                    if scale_elem is not None:
                        min_el = scale_elem.find("min")
                        max_el = scale_elem.find("max")
                        field_info["scale_min"] = float(min_el.text) if min_el is not None and min_el.text else 0
                        field_info["scale_max"] = float(max_el.text) if max_el is not None and max_el.text else 255

                # Parse command fields (similar to enum)
                elif field.tag == "command":
                    field_info["values"] = []
                    for item in field.findall("item"):
                        field_info["values"].append({
                            "value": item.get("value", ""),
                            "description": item.get("description", "")
                        })

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

    BUNDLED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "custom_eep")
    HIDDEN_FILE = ".hidden_bundled.yaml"

    @staticmethod
    def _content_hash(data: dict) -> str:
        """Comparable digest of a profile file's content, without our own
        bookkeeping key. Identifies which bundled version a user edit is
        based on."""
        import hashlib
        clean = {k: v for k, v in (data or {}).items() if k != "based_on_bundled"}
        return hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:16]

    @staticmethod
    def _eep_id_of(data: dict) -> Optional[str]:
        pd = (data or {}).get("profile") or {}
        rorg = str(pd.get("rorg", "")).upper()
        func = str(pd.get("func", "")).upper().zfill(2)
        type_ = str(pd.get("type", "")).upper().zfill(2)
        return f"{rorg}-{func}-{type_}" if rorg else None

    @staticmethod
    def _profile_from_data(data: dict) -> EEPProfile:
        pd = data["profile"]
        profile = EEPProfile(str(pd.get("rorg", "")).upper(),
                             str(pd.get("func", "")).upper().zfill(2),
                             str(pd.get("type", "")).upper().zfill(2),
                             pd.get("description", "Custom Profile"))
        profile.fields = pd.get("fields", [])
        profile.is_custom = True
        # HA mapping either top-level or inside the profile
        profile.ha_mapping = data.get("ha_mapping") or pd.get("ha_mapping") or {}
        return profile

    async def _read_yaml_dir(self, path: str) -> Dict[str, Dict[str, Any]]:
        found = {}
        if not os.path.isdir(path):
            return found
        for filename in sorted(os.listdir(path)):
            if not filename.endswith((".yaml", ".yml")) or filename.startswith("."):
                continue
            try:
                async with aiofiles.open(os.path.join(path, filename), 'r') as f:
                    data = yaml.safe_load(await f.read())
                eep_id = self._eep_id_of(data)
                if eep_id:
                    data["_file"] = filename
                    found[eep_id] = data
            except Exception as e:
                logger.error(f"Failed to load profile {filename}: {e}")
        return found

    async def _load_bundled_profiles(self):
        self.bundled = await self._read_yaml_dir(self.BUNDLED_PATH)
        for data in self.bundled.values():
            data.pop("_file", None)

    async def _load_hidden(self):
        path = os.path.join(self.custom_eep_path, self.HIDDEN_FILE)
        try:
            async with aiofiles.open(path, 'r') as f:
                self.hidden_bundled = set((yaml.safe_load(await f.read()) or {}).get("hidden", []))
        except FileNotFoundError:
            self.hidden_bundled = set()
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            self.hidden_bundled = set()

    async def _save_hidden(self):
        os.makedirs(self.custom_eep_path, exist_ok=True)
        path = os.path.join(self.custom_eep_path, self.HIDDEN_FILE)
        async with aiofiles.open(path, 'w') as f:
            await f.write(yaml.dump({"hidden": sorted(self.hidden_bundled)}, default_flow_style=False))

    async def _load_custom_profiles(self):
        """Read the user's profile files from persistent storage."""
        os.makedirs(self.custom_eep_path, exist_ok=True)
        self.user_data = await self._read_yaml_dir(self.custom_eep_path)
        self.user_files = {e: d.pop("_file") for e, d in self.user_data.items()}

    async def _drop_seeded_copies(self):
        """Retire the copies the old seeding wrote into /data.

        A copy that equals the bundled profile is just that copy: removing it
        lets the bundled one apply, and future versions of it arrive with the
        update. A copy that differs is the user's edit (made since the last
        start, the old seeding overwrote anything older): it stays, marked
        with the bundled version it was based on.
        """
        for eep_id, bundled in self.bundled.items():
            data = self.user_data.get(eep_id)
            if not data:
                continue
            path = os.path.join(self.custom_eep_path, self._user_file(eep_id))
            if self._content_hash(data) == self._content_hash(bundled):
                try:
                    os.remove(path)
                    logger.info(f"Profile {eep_id}: copy of the bundled version removed, bundled applies")
                except OSError as e:
                    logger.error(f"Failed to remove {path}: {e}")
                del self.user_data[eep_id]
                self.user_files.pop(eep_id, None)
            elif "based_on_bundled" not in data:
                data["based_on_bundled"] = self._content_hash(bundled)
                await self._write_user_file(eep_id, data)
                logger.info(f"Profile {eep_id}: your edit of the bundled profile is kept")

    def _user_file(self, eep_id: str) -> str:
        return self.user_files.get(eep_id, f"{eep_id}.yaml")

    async def _write_user_file(self, eep_id: str, data: Dict[str, Any]):
        os.makedirs(self.custom_eep_path, exist_ok=True)
        filename = self._user_file(eep_id)
        async with aiofiles.open(os.path.join(self.custom_eep_path, filename), 'w') as f:
            await f.write(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        self.user_files[eep_id] = filename

    def _apply(self, eep_id: str):
        """Put the effective profile for eep_id into self.profiles:
        the user's file, else the bundled one unless hidden, else EEP.xml."""
        eep_id = eep_id.upper()
        if eep_id in self.user_data:
            data = self.user_data[eep_id]
            profile = self._profile_from_data(data)
            if eep_id in self.bundled:
                profile.source = "bundled_modified"
                based_on = data.get("based_on_bundled")
                # As text: a hand-edited, all-digit value would load as a number.
                profile.bundled_newer = (based_on not in (None, "")
                                         and str(based_on) != self._content_hash(self.bundled[eep_id]))
            else:
                profile.source = "custom"
        elif eep_id in self.bundled and eep_id not in self.hidden_bundled:
            profile = self._profile_from_data(self.bundled[eep_id])
            profile.source = "bundled"
        elif eep_id in self.base_profiles:
            self.profiles[eep_id] = self.base_profiles[eep_id]
            return
        else:
            self.profiles.pop(eep_id, None)
            return
        self.profiles[eep_id] = profile
        logger.info(f"Loaded {profile.source.replace('_', ' ')} profile: {eep_id}"
                    f"{' with ha_mapping' if profile.ha_mapping else ''}")

    def get_hidden_bundled(self) -> List[Dict[str, str]]:
        """Bundled profiles the user removed, for the restore list."""
        return [{"eep_id": e, "description": self.bundled[e]["profile"].get("description", "")}
                for e in sorted(self.hidden_bundled) if e in self.bundled]

    async def restore_bundled_profile(self, eep_id: str) -> bool:
        eep_id = eep_id.upper()
        if eep_id not in self.hidden_bundled:
            return False
        self.hidden_bundled.discard(eep_id)
        await self._save_hidden()
        self._apply(eep_id)
        logger.info(f"Restored bundled profile: {eep_id}")
        return True

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

    async def save_custom_profile(self, profile_data: Dict[str, Any],
                                   ha_mapping: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        """Save a custom profile with optional HA mapping"""
        try:
            rorg = profile_data.get("rorg", "").upper()
            func = profile_data.get("func", "").upper().zfill(2)
            type_ = profile_data.get("type", "").upper().zfill(2)

            eep_id = f"{rorg}-{func}-{type_}"

            # Build YAML structure
            save_data = {"profile": profile_data}
            if ha_mapping:
                save_data["ha_mapping"] = ha_mapping
            if eep_id in self.bundled:
                # Remember which bundled version this edit started from, so a
                # later bundled change can be pointed out instead of applied.
                previous = self.user_data.get(eep_id, {}).get("based_on_bundled")
                save_data["based_on_bundled"] = previous or self._content_hash(self.bundled[eep_id])

            await self._write_user_file(eep_id, save_data)
            self.user_data[eep_id] = save_data
            if eep_id in self.hidden_bundled:
                self.hidden_bundled.discard(eep_id)
                await self._save_hidden()
            self._apply(eep_id)

            logger.info(f"Saved custom profile: {eep_id}"
                        f"{' with ha_mapping' if ha_mapping else ''}")
            return True

        except Exception as e:
            logger.error(f"Failed to save custom profile: {e}")
            return False

    async def delete_custom_profile(self, eep_id: str) -> Optional[str]:
        """Remove the user's say over a profile; returns what happened.

        - "deleted": the user's own profile is gone (EEP.xml applies again,
          if it has the profile)
        - "reset": the user's edit of a bundled profile is gone, the bundled
          version applies again; the edit is kept as <id>.yaml.bak
        - "hidden": a bundled profile the user never edited is removed and
          stays removed until restored
        None if there is nothing to delete or it failed.
        """
        eep_id = eep_id.upper()
        try:
            if eep_id in self.user_data:
                path = os.path.join(self.custom_eep_path, self._user_file(eep_id))
                if os.path.exists(path):
                    if eep_id in self.bundled:
                        os.replace(path, path + ".bak")
                    else:
                        os.remove(path)
                del self.user_data[eep_id]
                self.user_files.pop(eep_id, None)
                result = "reset" if eep_id in self.bundled else "deleted"
            elif eep_id in self.bundled and eep_id not in self.hidden_bundled:
                self.hidden_bundled.add(eep_id)
                await self._save_hidden()
                result = "hidden"
            else:
                return None
            self._apply(eep_id)
            logger.info(f"Profile {eep_id}: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete custom profile {eep_id}: {e}")
            return None

    # === Mapping Overrides ===

    def _overrides_file(self) -> str:
        return os.path.join(self.config_path, "mapping_overrides.yaml")

    def _legacy_overrides_file(self) -> str:
        return os.path.join(self.config_path, "mapping_overrides.json")

    async def _load_overrides(self) -> Dict[str, Any]:
        path = self._overrides_file()
        legacy_path = self._legacy_overrides_file()

        # One-time migration from JSON to YAML
        if not os.path.exists(path) and os.path.exists(legacy_path):
            try:
                async with aiofiles.open(legacy_path, 'r') as f:
                    data = json.loads(await f.read())
                await self._save_overrides(data)
                logger.info("Migrated mapping_overrides.json -> mapping_overrides.yaml")
                self._override_cache = data
                return data
            except Exception:
                return {}

        if not os.path.exists(path):
            return {}
        try:
            async with aiofiles.open(path, 'r') as f:
                data = yaml.safe_load(await f.read()) or {}
                self._override_cache = data
                return data
        except Exception:
            return {}

    async def _save_overrides(self, overrides: Dict[str, Any]):
        path = self._overrides_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        async with aiofiles.open(path, 'w') as f:
            await f.write(yaml.dump(overrides, default_flow_style=False, allow_unicode=True))
        self._override_cache = overrides

    def get_mapping_override_sync(self, eep_id: str) -> Optional[Dict[str, Any]]:
        """Get mapping override from in-memory cache (sync, for use by mapping_manager)"""
        return self._override_cache.get(eep_id.upper())

    async def get_mapping_override(self, eep_id: str) -> Optional[Dict[str, Any]]:
        """Get mapping override for an EEP profile (None if no override)"""
        overrides = await self._load_overrides()
        return overrides.get(eep_id.upper())

    async def save_mapping_override(self, eep_id: str, mapping: Dict[str, Dict[str, Any]]) -> bool:
        """Save a mapping override for an EEP profile"""
        try:
            overrides = await self._load_overrides()
            overrides[eep_id.upper()] = mapping
            await self._save_overrides(overrides)
            logger.info(f"Saved mapping override for {eep_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save mapping override for {eep_id}: {e}")
            return False

    async def delete_mapping_override(self, eep_id: str) -> bool:
        """Delete a mapping override, reverting to EEP.xml default"""
        try:
            overrides = await self._load_overrides()
            if eep_id.upper() not in overrides:
                return False
            del overrides[eep_id.upper()]
            await self._save_overrides(overrides)
            logger.info(f"Deleted mapping override for {eep_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete mapping override for {eep_id}: {e}")
            return False

    async def get_all_mapping_overrides(self) -> Dict[str, Any]:
        """Get all mapping overrides"""
        return await self._load_overrides()
