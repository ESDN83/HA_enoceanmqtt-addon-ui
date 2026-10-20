"""
Radiator valves that only listen right after they transmit (A5-20-01, e.g.
Micropelt MVA004 / SAM). ADR-0029.

The valve sends its state every few minutes and then listens for about one
second. A command at any other time is never heard, so the gateway answers
every telegram at once with the values Home Assistant last set. Pairing is a
4BS bidirectional teach-in: the valve sends a query and wants a response
within that same second.

Both formats follow the Micropelt datasheet and two independent
implementations (FHEM 10_EnOcean.pm, embyt enocean-mqtt):

- teach-in response: the query's DB3..DB1 (FUNC, TYPE, manufacturer)
  unchanged, DB0 = 0xF0, addressed to the valve, from the gateway sender the
  valve is to remember
- reply: DB3 setpoint (valve % or temperature over 0..255 = 0..40 C),
  DB2 room temperature (0x00 = use the valve's own sensor), DB1 summer bit
  0x08 and setpoint selection 0x04 (temperature), DB0 0x08 (data)
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import aiofiles
import yaml

logger = logging.getLogger(__name__)

VALVE_EEP = "A5-20-01"
TEACH_IN_RESPONSE_DB0 = 0xF0

MODE_VALVE = "valve"
MODE_TEMPERATURE = "temperature"
MODES = (MODE_VALVE, MODE_TEMPERATURE)

# Before anything is set the valve regulates itself to 21 C: an answer that
# closed the valve would switch the heating off on pairing.
DEFAULTS = {"mode": MODE_TEMPERATURE, "valve": 50, "temperature": 21.0, "summer": False}

# MQTT command entities: /set/<entity>
ENTITY_VALVE = "valve_setpoint"
ENTITY_TEMPERATURE = "target_temperature"
ENTITY_MODE = "mode"
ENTITY_SUMMER = "summer_mode"


def is_teach_in_query(data: bytes) -> bool:
    """4BS teach-in query with EEP: LRN bit 0, LRN type 1, status bits 0."""
    return len(data) == 4 and (data[3] & 0x08) == 0 and (data[3] & 0xF0) == 0x80


def query_eep(data: bytes) -> str:
    func = (data[0] >> 2) & 0x3F
    type_ = ((data[0] & 0x03) << 5) | ((data[1] >> 3) & 0x1F)
    return f"A5-{func:02X}-{type_:02X}"


def teach_in_response(query: bytes) -> bytes:
    return bytes(query[:3]) + bytes([TEACH_IN_RESPONSE_DB0])


def reply_payload(values: Dict[str, Any]) -> bytes:
    """The four data bytes the valve gets after each of its telegrams."""
    if values.get("mode") == MODE_TEMPERATURE:
        temp = min(max(float(values.get("temperature", 21.0)), 0.0), 40.0)
        setpoint = round(temp * 255 / 40)
        flags = 0x04
    else:
        setpoint = min(max(int(round(float(values.get("valve", 0)))), 0), 100)
        flags = 0x00
    if values.get("summer"):
        flags |= 0x08
    return bytes([setpoint, 0x00, flags, 0x08])


def is_valve(device) -> bool:
    return device is not None and str(device.eep_id).upper() == VALVE_EEP


class ValveControl:
    """Answers valve telegrams and keeps the values Home Assistant set."""

    def __init__(self, config_path: str, serial_handler, device_manager, mqtt_handler):
        self.serial_handler = serial_handler
        self.device_manager = device_manager
        self.mqtt_handler = mqtt_handler
        self._file = os.path.join(config_path, "valve_setpoints.yaml")
        self._values: Dict[str, Dict[str, Any]] = {}
        # Called with the device once teach-in gave it a sender ID: its
        # control entities exist only with one, so discovery is re-published.
        self.on_sender_assigned = None

    async def load(self):
        if not os.path.exists(self._file):
            return
        try:
            async with aiofiles.open(self._file, "r") as f:
                self._values = yaml.safe_load(await f.read()) or {}
        except Exception as e:
            logger.error(f"Could not read {self._file}: {e}")

    async def _save(self):
        try:
            async with aiofiles.open(self._file, "w") as f:
                await f.write(yaml.safe_dump(self._values, allow_unicode=True))
        except Exception as e:
            logger.error(f"Could not write {self._file}: {e}")

    def values(self, device_name: str) -> Dict[str, Any]:
        return dict(DEFAULTS, **self._values.get(device_name, {}))

    def state_fields(self, device_name: str) -> Dict[str, Any]:
        """The set values as they appear in the device's MQTT state."""
        v = self.values(device_name)
        return {
            "SET_MODE": v["mode"],
            "SET_VALVE": int(v["valve"]),
            "SET_TEMP": round(float(v["temperature"]), 1),
            "SET_SUMMER": "ON" if v["summer"] else "OFF",
        }

    def rename(self, old: str, new: str):
        if old in self._values:
            self._values[new] = self._values.pop(old)
            asyncio.create_task(self._save())

    # --- receive side -------------------------------------------------------

    def handle_rx(self, telegram, teach_in_active: bool) -> Optional[Dict[str, Any]]:
        """Called for every 4BS telegram before it is decoded.

        Returns teach-in details for the UI when the telegram was a valve's
        teach-in query (it must then not be decoded as data, its DB3 read as a
        valve position gave 128 %), otherwise None. Replies are sent in a task
        of their own: the read loop has to stay free to read the
        transceiver's acknowledgement of that very reply.
        """
        data = telegram.data
        device = self.device_manager.get_device_by_address(telegram.sender_hex)
        if is_teach_in_query(data):
            if query_eep(data) != VALVE_EEP:
                return None
            if device is not None and not is_valve(device):
                return None
            if device is None and not teach_in_active:
                logger.info(f"Valve teach-in from {telegram.sender_hex} ignored, no teach-in session")
                return None
            sender = self._sender_for(device)
            if sender is None:
                logger.warning(f"Valve teach-in from {telegram.sender_hex}: no free sender ID")
                return None
            if device is not None and not device.sender_id:
                asyncio.create_task(self._store_sender(device, sender))
            asyncio.create_task(self._send(sender, teach_in_response(data), telegram.sender_id,
                                           f"{device.name if device else telegram.sender_hex} teach-in response"))
            return {"response_sender": f"0x{sender:08X}"}

        if is_valve(device) and device.sender_id and (data[3] & 0x08):
            sender = int(device.sender_id.replace("0x", "").replace("0X", ""), 16)
            payload = reply_payload(self.values(device.name))
            asyncio.create_task(self._send(sender, payload, telegram.sender_id, f"{device.name} reply"))
        return None

    def _sender_for(self, device) -> Optional[int]:
        """The device's own sender, else the lowest gateway offset nobody uses.

        Eltako actuators act on a sender ID whatever the destination, so a
        valve must not share one with them.
        """
        if device is not None and device.sender_id:
            return int(device.sender_id.replace("0x", "").replace("0X", ""), 16)
        used = {str(d.sender_id).lower().replace("0x", "").zfill(8)
                for d in self.device_manager.devices.values() if d.sender_id}
        for offset in range(2, 128):
            sid = self.serial_handler.get_sender_id(offset)
            if sid is None:
                return None
            if f"{sid:08x}" not in used:
                return sid
        return None

    async def _store_sender(self, device, sender: int):
        device.sender_id = f"0x{sender:08X}"
        await self.device_manager.save_devices()
        logger.info(f"Valve {device.name}: sender ID 0x{sender:08X} stored at teach-in")
        if self.on_sender_assigned is not None:
            try:
                await self.on_sender_assigned(device)
            except Exception as e:
                logger.error(f"Valve {device.name}: discovery not re-published: {e}")
        await self._publish_set_values(device.name)

    async def _publish_set_values(self, device_name: str):
        """Put the set values into the retained state, the rest unchanged."""
        if self.mqtt_handler:
            state = dict(self.mqtt_handler.get_last_state(device_name) or {})
            state.update(self.state_fields(device_name))
            await self.mqtt_handler.publish_state(device_name, state)

    async def _send(self, sender: int, data: bytes, destination: int, label: str):
        try:
            await self.serial_handler.send_4bs_addressed(sender, data, destination, label)
        except Exception as e:
            logger.error(f"Valve {label} not sent: {e}")

    # --- Home Assistant side ------------------------------------------------

    async def handle_command(self, device, payload: str, entity: Optional[str]):
        """Store a value from Home Assistant; it goes out with the next reply."""
        v = self._values.setdefault(device.name, {})
        p = (payload or "").strip()
        try:
            if entity == ENTITY_VALVE:
                v["valve"] = min(max(int(round(float(p))), 0), 100)
                v["mode"] = MODE_VALVE
            elif entity == ENTITY_TEMPERATURE:
                v["temperature"] = round(min(max(float(p), 0.0), 40.0), 1)
                v["mode"] = MODE_TEMPERATURE
            elif entity == ENTITY_MODE:
                if p.lower() not in MODES:
                    raise ValueError(p)
                v["mode"] = p.lower()
            elif entity == ENTITY_SUMMER:
                v["summer"] = p.upper() in ("ON", "1", "TRUE")
            else:
                logger.warning(f"Valve {device.name}: unknown command entity {entity!r}")
                return
        except ValueError:
            logger.warning(f"Valve {device.name}: invalid value {payload!r} for {entity}")
            return
        await self._save()
        logger.info(f"Valve {device.name}: {entity} = {p}, sent with the next reply")
        await self._publish_set_values(device.name)
