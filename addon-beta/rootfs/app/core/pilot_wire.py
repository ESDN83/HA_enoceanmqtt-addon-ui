"""
Pilot wire heating modules (D2-01-0C, e.g. NodOn SIN-2-FP-21) and metering
D2-01 modules (e.g. NodOn Micro Smart Plug, D2-01-0E). ADR-0032, ADR-0035.

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

Every D2-01 type whose profile has the measurement commands (CMD 5/6/7 in
EEP.xml: 08, 09, 0B, 0C, 0E) is queried the same way, and gets Power and
Energy. A NodOn plug reports power on its own but energy only when asked
(issue #48). The query carries the device's channel in its IO field.

A reading that cannot be right (energy lower than before or rising faster
than the maximum load allows, power above it) is held back and asked for
again at once. It is published only when a second reading confirms it, so a
corrupted telegram is dropped and a real counter reset or a replaced module
still goes through. Home Assistant reads a falling total_increasing value as
a meter reset, so one corrupted value would spoil the energy statistics for
good (issue #51, ADR-0039).
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PILOT_EEP = "D2-01-0C"
MODES = ["Off", "Comfort", "Eco", "Anti-freeze", "Comfort-1", "Comfort-2"]
ENTITY_MODE = "pilot_wire_mode"

QUERY_MODE = bytes([0x09])
QUERY_POWER_BIT = 0x20  # CMD 6 byte 1: bit 5 power (else energy), IO below
POLL_SECONDS = 300
METER_FIELDS = ("POWER_W", "ENERGY_KWH")
# A D2-01 module switches at most 16 A; with margin, more than this is not a
# load it can measure. Only decides what gets a second look, so a real higher
# value still goes through once it is confirmed.
MAX_POWER_W = 4000.0
# Rounding and counter resolution: smaller differences are not a jump.
ENERGY_TOLERANCE_KWH = 0.01


def is_pilot(device) -> bool:
    return device is not None and str(device.eep_id).upper() == PILOT_EEP


def profile_meters(profile) -> bool:
    """A D2-01 profile with the actuator measurement response (CMD 7)."""
    if profile is None or not profile.eep_id.upper().startswith("D2-01-"):
        return False
    return any(str(f.get("command")) == "7" for f in profile.fields)


def query_payloads(channel: int = 0):
    """CMD 6 power and energy queries for one channel."""
    io = int(channel or 0) & 0x1F
    return bytes([0x06, QUERY_POWER_BIT | io]), bytes([0x06, io])


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
    """Sends mode commands to pilot wire modules and measurement queries to
    every metering D2-01 module."""

    def __init__(self, serial_handler, device_manager, mqtt_handler, eep_manager=None):
        self.serial_handler = serial_handler
        self.device_manager = device_manager
        self.mqtt_handler = mqtt_handler
        self.eep_manager = eep_manager
        self._task: Optional[asyncio.Task] = None
        # Per device: when the published energy was last accepted, and a
        # held-back reading waiting for its confirmation, as (value, time).
        self._energy_at: Dict[str, float] = {}
        self._held: Dict[tuple, tuple] = {}

    def meters(self, device) -> bool:
        if device is None or self.eep_manager is None:
            return is_pilot(device)
        return profile_meters(self.eep_manager.get_profile(str(device.eep_id).upper()))

    def merge_state(self, device, payload: Dict[str, Any]) -> Dict[str, Any]:
        """A reply carries the mode or one measurement; keep the others.

        Each published state replaces the retained one, so without this an
        energy reply would wipe the power value, and a switch status the
        last measurement. A measurement of another channel is not this
        device's.
        """
        last = self.mqtt_handler.get_last_state(device.name) if self.mqtt_handler else None
        merged = {k: v for k, v in (last or {}).items()
                  if k in ("PILOT_MODE",) + METER_FIELDS}
        merged.update(payload)
        io = payload.get("IO")
        if payload.get("CMD") != 7 or io is None or int(io) == int(getattr(device, "channel", 0) or 0):
            merged.update(self._checked(device, derived_state(payload), last or {}))
        return merged

    def _energy_ok(self, value: float, since: Optional[tuple]) -> bool:
        """value is a plausible successor of since = (kWh, time)."""
        if since is None or since[0] is None:
            return True
        before, at = since
        if value < before - ENERGY_TOLERANCE_KWH:
            return False
        if at is None:
            return True  # no time to measure the rise against
        hours = max(0.0, time.monotonic() - at) / 3600
        return value - before <= MAX_POWER_W / 1000 * hours + ENERGY_TOLERANCE_KWH

    def _checked(self, device, values: Dict[str, Any], last: Dict[str, Any]) -> Dict[str, Any]:
        """The readings that may be published now; the others are held back
        and asked for again."""
        out = dict(values)
        now = time.monotonic()
        if "ENERGY_KWH" in out:
            value = out["ENERGY_KWH"]
            key = (device.name, "energy")
            held = self._held.pop(key, None)
            last_value = last.get("ENERGY_KWH")
            previous = (float(last_value), self._energy_at.get(device.name)) if last_value is not None else None
            if self._energy_ok(value, previous):
                self._energy_at[device.name] = now
            elif held is not None and self._energy_ok(value, held):
                logger.info(f"{device.name}: energy {value} kWh confirmed by a second "
                            f"reading (was {last_value} kWh), taken as a counter reset")
                self._energy_at[device.name] = now
            else:
                logger.warning(f"{device.name}: energy {value} kWh after {last_value} kWh "
                               f"is implausible, held back and asked again")
                self._held[key] = (value, now)
                del out["ENERGY_KWH"]
                self._ask_again(device, energy=True)
        if "POWER_W" in out:
            value = out["POWER_W"]
            key = (device.name, "power")
            held = self._held.pop(key, None)
            if 0 <= value <= MAX_POWER_W:
                pass
            elif held is not None:
                logger.info(f"{device.name}: power {value} W confirmed by a second reading")
            else:
                logger.warning(f"{device.name}: power {value} W is implausible, "
                               f"held back and asked again")
                self._held[key] = (value, now)
                del out["POWER_W"]
                self._ask_again(device, energy=False)
        return out

    def _ask_again(self, device, energy: bool):
        power, energy_query = query_payloads(getattr(device, "channel", 0))
        data = energy_query if energy else power
        label = "energy query (check)" if energy else "power query (check)"

        async def later():
            # Not from inside the read loop: it must be free for the answer.
            await asyncio.sleep(0.5)
            await self._send(device, data, label)
        try:
            asyncio.get_running_loop().create_task(later())
        except RuntimeError:
            pass  # no loop (tests): the next poll asks again

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
        power, energy = query_payloads(getattr(device, "channel", 0))
        queries = [(power, "power query"), (energy, "energy query")]
        if is_pilot(device):
            queries.insert(0, (QUERY_MODE, "mode query"))
        for data, label in queries:
            await self._send(device, data, label)

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._poll())

    async def _poll(self):
        await asyncio.sleep(30)  # let the transceiver connect first
        while True:
            for device in list(self.device_manager.devices.values()):
                if not (self.meters(device) and device.sender_id):
                    continue
                # A poll that falls into a reconnect waits for it (#51).
                if not await self.serial_handler.wait_connected(5):
                    logger.warning(f"{device.name} not polled: transceiver not connected")
                    continue
                await self.query(device)
            await asyncio.sleep(POLL_SECONDS)
