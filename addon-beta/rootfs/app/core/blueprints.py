"""
Automation blueprints offered from the UI. Issue #57, ADR-0046.

Nothing is installed on its own: a blueprint that no automation uses is
reported as a problem by Spook. The UI offers one only when a matching device
is configured, and installs it on a button press through Home Assistant's
WebSocket API (blueprint/save), into blueprints/automation/enocean_mqtt_ui/.
An installed blueprint is never overwritten: the user may have edited it, and
re-importing from its source_url is Home Assistant's own update path.
"""

import os
from typing import Any, Callable, Dict, List

BLUEPRINT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "blueprints")
HA_FOLDER = "enocean_mqtt_ui"

_SMOKE_EEPS = {"F6-05-02", "D2-14-30"}


def _is_rocker(device, mapping_manager) -> bool:
    from core.rocker_events import is_rocker
    return is_rocker(device)


def _is_smoke(device, mapping_manager) -> bool:
    return str(device.eep_id).upper() in _SMOKE_EEPS


def _is_window(device, mapping_manager) -> bool:
    """A window contact, door contact or window handle. Not a valve that
    detects an open window itself, nor a unit whose flaps are "opening"."""
    from core.valve_control import is_valve
    eep = str(device.eep_id).upper()
    if eep == "F6-10-00":
        return True
    if is_valve(device):
        return False
    try:
        mapping = mapping_manager.get_mapping(eep) or {}
    except Exception:
        return False
    return any(f.get("component") == "binary_sensor"
               and f.get("device_class") in ("window", "door")
               for f in mapping.values() if isinstance(f, dict))


BLUEPRINTS: List[Dict[str, Any]] = [
    {"id": "rocker_light", "file": "enocean_rocker_light.yaml",
     "name": "Rocker controls a light", "match": _is_rocker},
    {"id": "smoke_notify", "file": "enocean_smoke_notify.yaml",
     "name": "Smoke alarm notification", "match": _is_smoke},
    {"id": "window_heating", "file": "enocean_window_heating.yaml",
     "name": "Window pauses heating", "match": _is_window},
]


def ha_path(bp: Dict[str, Any]) -> str:
    return f"{HA_FOLDER}/{bp['file']}"


def read_yaml(bp: Dict[str, Any]) -> str:
    with open(os.path.join(BLUEPRINT_DIR, bp["file"]), encoding="utf-8") as f:
        return f.read()


def matching_devices(bp: Dict[str, Any], devices, mapping_manager) -> List[str]:
    match: Callable = bp["match"]
    return sorted(d.name for d in devices if match(d, mapping_manager))


def find(bp_id: str) -> Dict[str, Any]:
    return next((bp for bp in BLUEPRINTS if bp["id"] == bp_id), None)
