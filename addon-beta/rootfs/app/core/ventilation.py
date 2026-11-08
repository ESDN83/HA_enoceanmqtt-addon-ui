"""
Ventilation units D2-50-00/01/10/11 (heat recovery, single and multi room).
Issue #61, ADR-0046.

The unit reports a basic status (MT 2) and an extended status (MT 3) and
takes a ventilation control telegram (MT 1). Formats from EEP.xml, cross-
checked against FHEM 10_EnOcean.pm (heatRecovery.00):

- control:       MT 1, 6 bytes: 0x20 | mode (DOMC), no operation mode
                 change, no timer, thresholds 127 (= the unit's own), room
                 temperature 0 (= the unit's own)
- status query:  MT 0, one byte: requested message type (0 basic, 1 extended)

The two status messages carry different fields, and a telegram replaces the
whole MQTT state, so the last state is merged in: otherwise the extended
status would turn every basic status entity unknown and back.

Pairing is UTE (bidirectional), which the serial handler answers for any D2
profile. A command needs the sender ID the unit was paired with.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

VENT_EEPS = ("D2-50-00", "D2-50-01", "D2-50-10", "D2-50-11")

# DOMC / OMS values
MODES = {
    "off": 0, "level 1": 1, "level 2": 2, "level 3": 3, "level 4": 4,
    "automatic": 11, "on demand": 12, "supply air only": 13, "exhaust air only": 14,
}
MODE_NAMES = {v: k for k, v in MODES.items()}

ENTITY_MODE = "ventilation_mode"
ENTITY_STATUS = "request_status"

_KEEP_CURRENT = 15
_DEFAULT_THRESHOLD = 127


def is_ventilation_eep(eep_id) -> bool:
    return str(eep_id or "").upper() in VENT_EEPS


def is_ventilation(device) -> bool:
    return device is not None and is_ventilation_eep(getattr(device, "eep_id", ""))


def control_payload(mode: int) -> bytes:
    """MT 1: set the mode, leave every other setting to the unit."""
    return bytes([0x20 | (mode & 0x0F), 0x00, _DEFAULT_THRESHOLD, _DEFAULT_THRESHOLD,
                  _DEFAULT_THRESHOLD, 0x00])


def status_query(extended: bool = False) -> bytes:
    """MT 0: ask for the basic (or extended) status."""
    return bytes([0x01 if extended else 0x00])


def merge_state(last: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the other status message's fields."""
    merged = {k: v for k, v in (last or {}).items() if not k.startswith("_")}
    merged.update(payload)
    if "OMS" in payload:
        merged["VENT_MODE"] = MODE_NAMES.get(int(payload["OMS"]), None)
    return merged


class Ventilation:
    def __init__(self, serial_handler, mqtt_handler):
        self.serial_handler = serial_handler
        self.mqtt_handler = mqtt_handler

    @staticmethod
    def _sender(device):
        try:
            return int(str(device.sender_id).replace("0x", "").replace("0X", ""), 16)
        except (TypeError, ValueError):
            return None

    async def handle_command(self, device, payload: str, entity: str) -> bool:
        """True when the command was this module's."""
        if entity not in (ENTITY_MODE, ENTITY_STATUS):
            return False
        sender = self._sender(device)
        if sender is None:
            logger.warning(f"Ventilation {device.name}: no sender ID, pair the unit first (UTE)")
            return True
        destination = int(device.address.replace("0x", "").replace("0X", ""), 16)
        if entity == ENTITY_STATUS:
            await self.serial_handler.send_vld_addressed(
                sender, status_query(), destination, f"{device.name} status query")
            return True
        mode = MODES.get((payload or "").strip().lower())
        if mode is None:
            logger.warning(f"Ventilation {device.name}: unknown mode {payload!r}")
            return True
        if await self.serial_handler.send_vld_addressed(
                sender, control_payload(mode), destination, f"{device.name} mode {payload}"):
            # The unit answers with its basic status; ask in case it does not.
            await self.serial_handler.send_vld_addressed(
                sender, status_query(), destination, f"{device.name} status query")
        return True


def discovery_configs(build_unique_id, eep_id, device_address, device_sender, device_name,
                      mqtt_prefix, device_info, avail_config) -> List[Dict[str, Any]]:
    """Mode select and status request button (needs a sender ID)."""
    state_topic = f"{mqtt_prefix}/{device_name}/state"
    out = []
    uid = build_unique_id(eep_id, device_address, device_sender, "VENT_MODE")
    out.append({"component": "select", "unique_id": uid, "config": {
        "name": "Ventilation Mode",
        "unique_id": uid,
        "object_id": f"{device_name}_ventilation_mode".lower().replace(" ", "_"),
        "state_topic": state_topic,
        "value_template": "{{ value_json.VENT_MODE if value_json.VENT_MODE is defined and value_json.VENT_MODE else None }}",
        "command_topic": f"{mqtt_prefix}/{device_name}/set/{ENTITY_MODE}",
        "options": list(MODES),
        "icon": "mdi:fan",
        "device": device_info,
        "availability": avail_config,
    }})
    uid = build_unique_id(eep_id, device_address, device_sender, "VENT_STATUS")
    out.append({"component": "button", "unique_id": uid, "config": {
        "name": "Request Status",
        "unique_id": uid,
        "object_id": f"{device_name}_request_status".lower().replace(" ", "_"),
        "command_topic": f"{mqtt_prefix}/{device_name}/set/{ENTITY_STATUS}",
        "payload_press": "PRESS",
        "entity_category": "diagnostic",
        "icon": "mdi:refresh",
        "device": device_info,
        "availability": avail_config,
    }})
    return out
