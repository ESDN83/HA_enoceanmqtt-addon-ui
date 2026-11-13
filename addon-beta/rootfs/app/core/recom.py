"""
Remote Commissioning: pair an actuator with the app from its QR code, without
a button press on the device (OPUS BRiDGE and other ReCom devices). Issue
#67, ADR-0047.

From the public EnOcean specifications Remote Management v2.7 (SYS_EX,
RMCC) and Remote Commissioning v1.5 (link tables); no other implementation's
code is used.

SYS_EX (RORG 0xC5), one message in chained telegrams: msg_id (SEQ 2 bits,
IDX 6 bits), then for IDX 0 data length (9 bits), manufacturer ID (11 bits),
function (12 bits) and 4 payload bytes, for IDX > 0 8 payload bytes. The
data field is always 8 bytes, filled from the left: an ERP1 SYS_EX telegram
is 16 bytes long. 1.8.7-beta2/3 sent shorter ones, and real OPUS BRiDGE
devices did not answer them (forum, post 20).

Since 1.8.7-beta8 the commands go to the transceiver as ESP3
REMOTE_MAN_COMMAND (packet type 7) first: the module builds the SYS_EX
telegrams itself and hands answers back already decoded, as EnOcean's own
tools and FHEM do. A real 563.010 answered none of the app-built telegrams,
and this takes the app's bit packing out of the question. A module or
gateway that does not support it gets the app-built SYS_EX telegrams as
before. ADR-0051.

Pairing:
1. UNLOCK (0x001) with the security code from the QR label, twice
2. PING (0x006), the answer (0x606) shows the device listens
3. link table metadata (0x210 -> 0x810) and the inbound table (0x211 -> 0x811)
4. nothing to do if the app's sender ID is in it already
5. otherwise SET LINK TABLE (0x212) at the first index after the used ones,
   so no wall switch the device has learned is overwritten, then APPLY
   CHANGES (0x226); both acknowledged with 0x240
6. LOCK (0x002)

The security code unlocks the device: it is used for this run only, never
stored and never logged.
"""

import asyncio
import logging
import random
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

RORG_SYS_EX = 0xC5
MANUFACTURER_MULTI = 0x7FF

FN_UNLOCK = 0x001
FN_LOCK = 0x002
FN_PING = 0x006
FN_PING_RESPONSE = 0x606
FN_QUERY_STATUS = 0x008
FN_QUERY_STATUS_RESPONSE = 0x608
FN_LINK_META = 0x210
FN_LINK_META_RESPONSE = 0x810
FN_GET_LINK = 0x211
FN_GET_LINK_RESPONSE = 0x811
FN_SET_LINK = 0x212
FN_APPLY = 0x226
FN_ACK = 0x240

_QR = re.compile(r"30S[0-9A-F]{4}([0-9A-F]{8})\+1P([0-9A-F]+)(?:\+.*?)?\+11Z([0-9A-F]{8})", re.I)


def eep_from_ping(answer: bytes) -> Optional[str]:
    """The device's own EEP from a PING answer (0x606): RORG 8 bits, FUNC 6,
    TYPE 7, as FHEM decodes it. A real 563.010 answers d2 04 08 = D2-01-01."""
    if len(answer) < 3:
        return None
    v = int.from_bytes(answer[:3], "big") >> 3
    rorg, func, type_ = v >> 13, (v >> 7) & 0x3F, v & 0x7F
    if rorg == 0:
        return None
    return f"{rorg:02X}-{func:02X}-{type_:02X}"


def parse_qr(text: str) -> Optional[Dict[str, Any]]:
    """Address, product ID and security code from the QR label text, e.g.
    30S0000AAAAAAAA+1P...+10Z00+11ZCCCCCCCC."""
    m = _QR.search((text or "").strip().replace(" ", ""))
    if not m:
        return None
    return {"address": f"0x{m.group(1).upper()}", "product": m.group(2).upper(),
            "code": int(m.group(3), 16)}


# --- SYS_EX framing -----------------------------------------------------------

def sysex_telegrams(function: int, payload: bytes, seq: int,
                    manufacturer: int = MANUFACTURER_MULTI) -> List[bytes]:
    """The data fields (msg_id + up to 8 bytes) of one SYS_EX message."""
    header = ((len(payload) & 0x1FF) << 23) | ((manufacturer & 0x7FF) << 12) | (function & 0xFFF)
    first = header.to_bytes(4, "big") + payload[:4]
    out = [bytes([(seq << 6) | 0]) + first.ljust(8, b"\x00")]
    rest = payload[4:]
    idx = 1
    while rest:
        out.append(bytes([(seq << 6) | idx]) + rest[:8].ljust(8, b"\x00"))
        rest = rest[8:]
        idx += 1
    return out


class SysExReceiver:
    """Merges chained SYS_EX telegrams into messages, per sender and SEQ."""

    def __init__(self):
        self._parts: Dict[Tuple[int, int], Dict[int, bytes]] = {}

    def feed(self, sender: int, data: bytes) -> Optional[Tuple[int, int, bytes]]:
        """(function, manufacturer, payload) once a message is complete."""
        if len(data) < 2:
            return None
        seq, idx = data[0] >> 6, data[0] & 0x3F
        key = (sender, seq)
        parts = self._parts.setdefault(key, {})
        parts[idx] = data[1:]
        first = parts.get(0)
        if first is None or len(first) < 4:
            return None
        header = int.from_bytes(first[:4], "big")
        length, manufacturer, function = header >> 23, (header >> 12) & 0x7FF, header & 0xFFF
        payload = first[4:]
        i = 1
        while len(payload) < length:
            if i not in parts:
                return None
            payload += parts[i]
            i += 1
        del self._parts[key]
        return function, manufacturer, payload[:length]


# --- pairing ------------------------------------------------------------------

class RecomError(Exception):
    pass


class Recom:
    def __init__(self, serial_handler):
        self.serial_handler = serial_handler
        self.receiver = SysExReceiver()
        self._waiters: List[Tuple[int, int, asyncio.Future]] = []
        # "esp3" (REMOTE_MAN_COMMAND), "sysex" (app-built telegrams) or None
        # until the transceiver has answered the first command.
        self.mode: Optional[str] = None

    def handle_rx(self, telegram) -> bool:
        """Called for every SYS_EX telegram; True when it was handled."""
        msg = self.receiver.feed(telegram.sender_id, telegram.data)
        if msg is None:
            return True
        function, manufacturer, payload = msg
        self.handle_message(telegram.sender_id, function, payload)
        return True

    def handle_message(self, source: int, function: int, payload: bytes):
        """One complete answer, from SYS_EX telegrams or decoded by the module."""
        logger.debug(f"ReCom answer from 0x{source:08X}: fn 0x{function:03X}, {len(payload)} bytes")
        for waiter in list(self._waiters):
            sender, fn, fut = waiter
            if sender == source and fn == function and not fut.done():
                fut.set_result(payload)
                self._waiters.remove(waiter)

    async def _send(self, sender: int, destination: int, function: int, payload: bytes = b""):
        secret = function in (FN_UNLOCK, FN_LOCK)
        label = f"ReCom fn 0x{function:03X}"
        if self.mode != "sysex":
            rc = await self.serial_handler.send_remote_man(
                function, MANUFACTURER_MULTI, payload, destination, label, secret=secret)
            if rc == 0:
                self.mode = "esp3"
                return
            if self.mode == "esp3":
                raise RecomError(f"transceiver did not take function 0x{function:03X}")
            reason = "no answer" if rc < 0 else f"return code 0x{rc:02X}"
            logger.info(f"Transceiver does not take remote management commands ({reason}), "
                        "sending SYS_EX telegrams instead")
            self.mode = "sysex"
        seq = random.randint(1, 3)  # SEQ 0 is not allowed
        for part in sysex_telegrams(function, payload, seq):
            if not await self.serial_handler.send_radio_addressed(
                    RORG_SYS_EX, sender, part, destination, label, secret=secret):
                raise RecomError(f"transceiver did not take function 0x{function:03X}")

    async def _ask(self, sender: int, destination: int, function: int, payload: bytes,
                   answer: int, timeout: float = 3.0, tries: int = 3) -> bytes:
        for _ in range(tries):
            fut = asyncio.get_running_loop().create_future()
            entry = (destination, answer, fut)
            self._waiters.append(entry)
            try:
                await self._send(sender, destination, function, payload)
                return await asyncio.wait_for(fut, timeout)
            except asyncio.TimeoutError:
                continue
            finally:
                if entry in self._waiters:
                    self._waiters.remove(entry)
        raise RecomError(f"no answer to function 0x{function:03X}")

    async def pair(self, destination: int, code: int, sender: int, eep: str,
                   channel: int = 0) -> Dict[str, Any]:
        """Put the app's sender ID into the device's inbound link table."""
        steps = []
        result: Dict[str, Any] = {}
        code_bytes = code.to_bytes(4, "big")
        try:
            for _ in range(2):  # recommended: repeat UNLOCK
                await self._send(sender, destination, FN_UNLOCK, code_bytes)
                await asyncio.sleep(0.2)
            steps.append("unlocked")
            logger.info(f"ReCom 0x{destination:08X}: commands sent as "
                        f"{'ESP3 remote management' if self.mode == 'esp3' else 'SYS_EX telegrams'}")
            pong = await self._ask(sender, destination, FN_PING, b"", FN_PING_RESPONSE)
            steps.append("ping answered")
            # The device only accepts a link table entry with an EEP it
            # supports: a 563.010 refused D2-01-00 and took D2-01-01, the
            # EEP its ping answer reports. Use that one.
            reported = eep_from_ping(pong)
            if reported:
                result["device_eep"] = reported
                steps.append(f"device reports EEP {reported}")
                if reported.upper() != str(eep).upper():
                    logger.warning(f"ReCom 0x{destination:08X}: configured profile {eep}, "
                                   f"the device reports {reported}; using {reported}")
                eep = reported
            rorg, func, type_ = (int(x, 16) for x in eep.split("-"))
            meta = await self._ask(sender, destination, FN_LINK_META, b"", FN_LINK_META_RESPONSE)
            if len(meta) < 5:
                raise RecomError("short link table metadata")
            if not meta[0] & 0x10:
                raise RecomError("the device has no inbound link table")
            used, size = meta[3], meta[4]
            steps.append(f"inbound link table {used} of {size} used")
            entries = []
            if used:
                table = await self._ask(sender, destination, FN_GET_LINK,
                                        bytes([0x00, 0, used - 1]), FN_GET_LINK_RESPONSE)
                body = table[1:]
                for i in range(0, len(body) - 8, 9):
                    e = body[i:i + 9]
                    entries.append({"index": e[0], "id": int.from_bytes(e[1:5], "big"),
                                    "eep": f"{e[5]:02X}-{e[6]:02X}-{e[7]:02X}", "channel": e[8]})
            if any(e["id"] == sender for e in entries):
                steps.append("sender already linked, nothing written")
                return {"status": "already_linked", "steps": steps, **result}
            if used >= size:
                raise RecomError(f"inbound link table full ({used} of {size})")
            index = max([e["index"] for e in entries], default=used - 1) + 1
            entry = bytes([index]) + sender.to_bytes(4, "big") + bytes([rorg, func, type_, channel & 0xFF])
            try:
                await self._ask(sender, destination, FN_SET_LINK, bytes([0x00]) + entry, FN_ACK)
            except RecomError:
                raise RecomError(f"the device did not accept the link table entry "
                                 f"(sender 0x{sender:08X}, EEP {eep})")
            steps.append(f"sender 0x{sender:08X} written at index {index}")
            # Not every device acknowledges APPLY CHANGES (a 563.010 does not,
            # and switched from the new sender right after); FHEM does not
            # wait for an answer either. The acknowledged entry counts.
            try:
                await self._ask(sender, destination, FN_APPLY, bytes([0x80]), FN_ACK,
                                timeout=2.0, tries=1)
                steps.append("changes applied")
            except RecomError:
                steps.append("apply changes sent, the device does not acknowledge it")
            return {"status": "paired", "steps": steps, "index": index, **result}
        finally:
            try:
                await self._send(sender, destination, FN_LOCK, code_bytes)
            except Exception as e:
                logger.warning(f"ReCom lock of 0x{destination:08X} not sent: {e}")
