"""
Pilot wire heating modules (D2-01-0C, e.g. NodOn SIN-2-FP-21). ADR-0032.

The module takes a pilot wire mode and measures power and energy. Formats
from EEP D2-01 as EEP.xml and Jeedom's profile describe it, and as FHEM
10_EnOcean.pm sends it:

- set mode:      CMD 8,  "08 0M"  (M: 0 Off, 1 Comfort, 2 Eco, 3 Anti-freeze,
                                   4 Comfort-1, 5 Comfort-2)
- query mode:    CMD 9,  "09"     -> reply CMD 10 "0A 0M"
- query value:   CMD 6,  "06 00" energy / "06 20" power (bit 5 = power)
                                  -> reply CMD 7: unit (0 Ws, 1 Wh, 2 kWh,
                                     3 W, 4 kW) and a 32-bit value

The module answers queries but does not report power or energy by itself
unless configured to (CMD 5), which would change its stored settings. The
app asks instead: after a mode change and every few minutes.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PILOT_EEP = "D2-01-0C"
MODES = ["Off", "Comfort", "Eco", "Anti-freeze", "Comfort-1", "Comfort-2"]
ENTITY_MODE = "pilot_wire_mode"

QUERY_MODE = bytes([0x09])
QUERY_ENERGY = bytes([0x06, 0x00])
QUERY_POWER = bytes([0x06, 0x20])
POLL_SECONDS = 300


def is_pilot(device) -> bool:
    return device is not None and str(device.eep_id).upper() == PILOT_EEP


def set_mode_payload(mode: str) -> bytes:
    idx = [m.lower() for m in MODES].index(mode.strip().lower())
    return bytes([0x08, idx])


def derived_state(decoded: Dict[str, Any]) -> Dict[str, Any]:
    """Mode, power (W) and energy (kWh) from a decoded CMD 10 / CMD 7 reply."""
    out: Dict[str, Any] = {}
    cmd = decoded.get("CMD")
    if cmd == 10 and decoded.get("PM") is not None:
        pm = int(decoded["PM"])
        if 0 <= pm < len(MODES):
            out["PILOT_MODE"] = MODES[pm]
    elif cmd == 7 and decoded.get("MV") is not None and decoded.get("UN") is not None:
        value, unit = float(decoded["MV"]), int(decoded["UN"])
        if unit == 0:
            out["ENERGY_KWH"] = round(value / 3_600_000, 3)
        elif unit == 1:
            out["ENERGY_KWH"] = round(value / 1000, 3)
        elif unit == 2:
            out["ENERGY_KWH"] = round(value, 3)
        elif unit == 3:
            out["POWER_W"] = round(value, 1)
        elif unit == 4:
            out["POWER_W"] = round(value * 1000, 1)
    return out


class PilotWire:
    """Sends mode commands and measurement queries to pilot wire modules."""

    def __init__(self, serial_handler, device_manager, mqtt_handler):
        self.serial_handler = serial_handler
        self.device_manager = device_manager
        self.mqtt_handler = mqtt_handler
        self._task: Optional[asyncio.Task] = None

    def merge_state(self, device_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """A reply carries the mode or one measurement; keep the others.

        Each published state replaces the retained one, so without this an
        energy reply would wipe the power value and the other way round.
        """
        last = self.mqtt_handler.get_last_state(device_name) if self.mqtt_handler else None
        merged = {k: v for k, v in (last or {}).items()
                  if k in ("PILOT_MODE", "POWER_W", "ENERGY_KWH")}
        merged.update(payload)
        merged.update(derived_state(payload))
        return merged

    async def _send(self, device, data: bytes, label: str) -> bool:
        try:
            sender = int(device.sender_id.replace("0x", "").replace("0X", ""), 16)
            dest = int(device.address.replace("0x", "").replace("0X", ""), 16)
        except (AttributeError, ValueError):
            logger.warning(f"Pilot wire {device.name}: no usable sender ID or address")
            return False
        try:
            return bool(await self.serial_handler.send_vld_addressed(
                sender, data, dest, f"{device.name} {label}"))
        except Exception as e:
            logger.error(f"Pilot wire {device.name} {label} not sent: {e}")
            return False

    async def set_mode(self, device, mode: str):
        try:
            data = set_mode_payload(mode)
        except ValueError:
            logger.warning(f"Pilot wire {device.name}: unknown mode {mode!r}")
            return
        if await self._send(device, data, f"mode {mode}"):
            # Read back what the module took, and the power that goes with it.
            await asyncio.sleep(1.0)
            await self.query(device)

    async def query(self, device):
        for data, label in ((QUERY_MODE, "mode query"), (QUERY_POWER, "power query"),
                            (QUERY_ENERGY, "energy query")):
            await self._send(device, data, label)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._poll())

    async def _poll(self):
        await asyncio.sleep(30)  # let the transceiver connect first
        while True:
            for device in list(self.device_manager.devices.values()):
                if is_pilot(device) and device.sender_id and self.serial_handler.is_connected:
                    await self.query(device)
            await asyncio.sleep(POLL_SECONDS)
