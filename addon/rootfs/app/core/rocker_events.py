"""
Rocker switch button events (F6-02-01 / F6-02-02). Issue #56, ADR-0042.

A rocker press is momentary: the existing Button AI/AO/BI/BO binary sensors
go ON and OFF again, and an automation has to watch their state. Home
Assistant's own model for a button is an event, so every press and release
is also published as one:

- `{prefix}/{device}/event`, NOT retained, payload
  `{"event_type": "AO_press", "button": "AO", "action": "press"}`
- an `event` entity listens to it (one per device, all buttons)
- one MQTT device trigger per button and action, so automations can be
  built from the device page without templates

The state topic cannot carry this. It is retained and republished at every
start, and a device trigger on it would fire for a press that happened
hours ago.

Actions per button:

- press         the button went down
- release       released before LONG_PRESS_S
- long_press    still held after LONG_PRESS_S (fires while held)
- long_release  released after a long_press

An RPS release telegram (EB = 0) does not say which button was let go, so
the buttons of the last press are remembered per device. A press telegram
with NU = 0 (three or four buttons at once) names no button and is skipped.
A repeated telegram (repeater, or two transceivers) for buttons that are
already held is ignored, so a repeater cannot fire a second press.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ROCKER_EEPS = {"F6-02-01", "F6-02-02"}
# R1/R2 per EEP F6-02-0x: 0 = AI, 1 = AO, 2 = BI, 3 = BO.
BUTTONS = ("AI", "AO", "BI", "BO")
LONG_PRESS_S = 0.6
# action -> Home Assistant device trigger type
TRIGGER_TYPES = {
    "press": "button_short_press",
    "release": "button_short_release",
    "long_press": "button_long_press",
    "long_release": "button_long_release",
}
EVENT_TYPES = [f"{b}_{a}" for b in BUTTONS for a in TRIGGER_TYPES]

_NU = 0x10  # RPS status bit: 1 = normal message (buttons are named)


def is_rocker_eep(eep_id: str) -> bool:
    return str(eep_id or "").upper() in ROCKER_EEPS


def is_rocker(device) -> bool:
    """Sensor-mode rocker. An actuator taught in as F6 sends confirmations
    from its address, not button presses."""
    return not getattr(device, "actuator_type", "") and is_rocker_eep(getattr(device, "eep_id", ""))


def pressed_buttons(decoded: Dict[str, Any], status: int) -> Optional[List[str]]:
    """Buttons held by this telegram, [] for a release, None if it is not
    a rocker telegram we can attribute."""
    eb = decoded.get("EB")
    if eb is None:
        return None
    if int(eb) == 0:
        return []
    if not status & _NU:
        return None
    buttons = []
    for field, gate in (("R1", True), ("R2", decoded.get("SA") == 1)):
        code = decoded.get(field)
        if gate and code is not None and 0 <= int(code) < len(BUTTONS):
            name = BUTTONS[int(code)]
            if name not in buttons:
                buttons.append(name)
    return buttons or None


class RockerEvents:
    def __init__(self, mqtt_handler):
        self.mqtt_handler = mqtt_handler
        # device name -> {"buttons", "since", "long", "timer"}
        self._held: Dict[str, Dict[str, Any]] = {}

    def topic(self, device_name: str) -> str:
        return f"{self.mqtt_handler.prefix}/{device_name}/event"

    async def _publish(self, device_name: str, buttons: List[str], action: str):
        for button in buttons:
            payload = {"event_type": f"{button}_{action}", "button": button, "action": action}
            await self.mqtt_handler.publish(self.topic(device_name), payload, retain=False)
            logger.debug(f"Rocker event [{device_name}] {button}_{action}")

    async def _long_press(self, device_name: str, held: Dict[str, Any]):
        await asyncio.sleep(LONG_PRESS_S)
        if self._held.get(device_name) is held:
            held["long"] = True
            await self._publish(device_name, held["buttons"], "long_press")

    async def handle(self, device, decoded: Dict[str, Any], status: int):
        buttons = pressed_buttons(decoded, status)
        if buttons is None:
            return
        name = device.name
        held = self._held.get(name)

        if buttons:
            if held is not None and held["buttons"] == buttons:
                return  # repeated telegram of the press already being held
            if held is not None:
                # A new press without a release in between: the release was
                # lost. Close the old one quietly rather than guess.
                held["timer"].cancel()
            held = {"buttons": buttons, "since": time.monotonic(), "long": False}
            self._held[name] = held
            held["timer"] = asyncio.create_task(self._long_press(name, held))
            await self._publish(name, buttons, "press")
            return

        if held is None:
            return  # release without a press we saw (or a repeated release)
        del self._held[name]
        held["timer"].cancel()
        await self._publish(name, held["buttons"], "long_release" if held["long"] else "release")


def discovery_configs(build_unique_id, eep_id: str, device_address: str, device_sender: str,
                      device_name: str, mqtt_prefix: str, device_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The event entity and the device triggers of one rocker."""
    topic = f"{mqtt_prefix}/{device_name}/event"
    event_uid = build_unique_id(eep_id, device_address, device_sender, "event")
    configs = [{
        "component": "event",
        "unique_id": event_uid,
        "config": {
            "name": "Button",
            "unique_id": event_uid,
            "object_id": f"{device_name}_button".lower().replace(" ", "_"),
            "state_topic": topic,
            "event_types": EVENT_TYPES,
            "device_class": "button",
            "icon": "mdi:gesture-tap-button",
            "device": device_info,
        },
    }]
    for button in BUTTONS:
        for action, trigger_type in TRIGGER_TYPES.items():
            uid = build_unique_id(eep_id, device_address, device_sender, f"trigger_{button}_{action}")
            configs.append({
                "component": "device_automation",
                "unique_id": uid,
                "config": {
                    "automation_type": "trigger",
                    "topic": topic,
                    "type": trigger_type,
                    "subtype": f"Button {button}",
                    "payload": f"{button}_{action}",
                    "value_template": "{{ value_json.event_type }}",
                    "device": device_info,
                },
            })
    return configs
