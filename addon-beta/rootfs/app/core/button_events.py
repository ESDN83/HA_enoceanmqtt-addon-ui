"""
Button events of D2-03-0A (single push button, e.g. NodOn Soft Button) and
of the two buttons of D2-06-01 window sensors. ADR-0055.

Same model as rocker_events (ADR-0042): non-retained
`{prefix}/{device}/event`, one event entity, one device trigger per action.
"""

import logging
import time
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_PUSH = {1: "press", 2: "double_press", 3: "long_press", 4: "long_release"}
_WINDOW = {1: "press", 2: "release"}
# EEP -> (field, button name, code -> action)
_FIELDS = {
    "D2-03-0A": [("BA", "Button", _PUSH)],
    "D2-06-01": [("BR", "Right", _WINDOW), ("BL", "Left", _WINDOW)],
}
_TYPES = {"press": "button_short_press", "release": "button_short_release",
          "double_press": "button_double_press", "long_press": "button_long_press",
          "long_release": "button_long_release"}
REPEAT_S = 0.3  # the same telegram again: a repeater


def has_button_events(eep_id) -> bool:
    return str(eep_id or "").upper() in _FIELDS


def _actions(eep_id) -> List[Tuple[str, str]]:
    return [(button, action) for _, button, codes in _FIELDS[str(eep_id).upper()]
            for action in codes.values()]


class ButtonEvents:
    def __init__(self, mqtt_handler):
        self.mqtt_handler = mqtt_handler
        self._last: Dict[Tuple[str, str], Tuple[str, float]] = {}

    async def handle(self, device, decoded: Dict[str, Any]):
        for field, button, codes in _FIELDS[str(device.eep_id).upper()]:
            action = codes.get(decoded.get(field))
            if action is None:
                continue
            key, now = (device.name, button), time.monotonic()
            last = self._last.get(key)
            if last and last[0] == action and now - last[1] < REPEAT_S:
                continue
            self._last[key] = (action, now)
            await self.mqtt_handler.publish(
                f"{self.mqtt_handler.prefix}/{device.name}/event",
                {"event_type": f"{button}_{action}", "button": button, "action": action}, retain=False)
            logger.debug(f"Button event [{device.name}] {button}_{action}")


def discovery_configs(build_unique_id, eep_id, device_address, device_sender, device_name,
                      mqtt_prefix, device_info) -> List[Dict[str, Any]]:
    topic = f"{mqtt_prefix}/{device_name}/event"
    uid = build_unique_id(eep_id, device_address, device_sender, "event")
    actions = _actions(eep_id)
    out = [{"component": "event", "unique_id": uid, "config": {
        "name": "Button", "unique_id": uid,
        "object_id": f"{device_name}_button".lower().replace(" ", "_"),
        "state_topic": topic, "event_types": [f"{b}_{a}" for b, a in actions],
        "device_class": "button", "icon": "mdi:gesture-tap-button", "device": device_info}}]
    for button, action in actions:
        uid = build_unique_id(eep_id, device_address, device_sender, f"trigger_{button}_{action}")
        out.append({"component": "device_automation", "unique_id": uid, "config": {
            "automation_type": "trigger", "topic": topic, "type": _TYPES[action],
            "subtype": button, "payload": f"{button}_{action}",
            "value_template": "{{ value_json.event_type }}", "device": device_info}})
    return out
