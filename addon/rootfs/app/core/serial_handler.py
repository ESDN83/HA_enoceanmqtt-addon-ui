"""
Serial Handler - Handles EnOcean serial/TCP communication
Based on ESP3 protocol

Uses a dedicated thread for serial I/O to avoid blocking the asyncio event loop.
"""

import os
import logging
import asyncio
import serial
import socket
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ESP3 Protocol constants
SYNC_BYTE = 0x55
PACKET_TYPE_RADIO = 0x01
PACKET_TYPE_RESPONSE = 0x02
PACKET_TYPE_EVENT = 0x04
PACKET_TYPE_COMMON_COMMAND = 0x05

# Common commands
CO_RD_IDBASE = 0x08


class TransceiverError(Exception):
    """Base class for EnOcean transceiver command failures."""


class NotConnectedError(TransceiverError):
    """Raised when a command is attempted with no active transport."""


class CommandTimeoutError(TransceiverError):
    """Raised when a command was sent but no response arrived in time."""


class TransportLostError(TransceiverError):
    """Raised when the transport died while a command was in flight."""


# CRC8 lookup table
CRC8_TABLE = [
    0x00, 0x07, 0x0e, 0x09, 0x1c, 0x1b, 0x12, 0x15, 0x38, 0x3f, 0x36, 0x31, 0x24, 0x23, 0x2a, 0x2d,
    0x70, 0x77, 0x7e, 0x79, 0x6c, 0x6b, 0x62, 0x65, 0x48, 0x4f, 0x46, 0x41, 0x54, 0x53, 0x5a, 0x5d,
    0xe0, 0xe7, 0xee, 0xe9, 0xfc, 0xfb, 0xf2, 0xf5, 0xd8, 0xdf, 0xd6, 0xd1, 0xc4, 0xc3, 0xca, 0xcd,
    0x90, 0x97, 0x9e, 0x99, 0x8c, 0x8b, 0x82, 0x85, 0xa8, 0xaf, 0xa6, 0xa1, 0xb4, 0xb3, 0xba, 0xbd,
    0xc7, 0xc0, 0xc9, 0xce, 0xdb, 0xdc, 0xd5, 0xd2, 0xff, 0xf8, 0xf1, 0xf6, 0xe3, 0xe4, 0xed, 0xea,
    0xb7, 0xb0, 0xb9, 0xbe, 0xab, 0xac, 0xa5, 0xa2, 0x8f, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9d, 0x9a,
    0x27, 0x20, 0x29, 0x2e, 0x3b, 0x3c, 0x35, 0x32, 0x1f, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0d, 0x0a,
    0x57, 0x50, 0x59, 0x5e, 0x4b, 0x4c, 0x45, 0x42, 0x6f, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7d, 0x7a,
    0x89, 0x8e, 0x87, 0x80, 0x95, 0x92, 0x9b, 0x9c, 0xb1, 0xb6, 0xbf, 0xb8, 0xad, 0xaa, 0xa3, 0xa4,
    0xf9, 0xfe, 0xf7, 0xf0, 0xe5, 0xe2, 0xeb, 0xec, 0xc1, 0xc6, 0xcf, 0xc8, 0xdd, 0xda, 0xd3, 0xd4,
    0x69, 0x6e, 0x67, 0x60, 0x75, 0x72, 0x7b, 0x7c, 0x51, 0x56, 0x5f, 0x58, 0x4d, 0x4a, 0x43, 0x44,
    0x19, 0x1e, 0x17, 0x10, 0x05, 0x02, 0x0b, 0x0c, 0x21, 0x26, 0x2f, 0x28, 0x3d, 0x3a, 0x33, 0x34,
    0x4e, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5c, 0x5b, 0x76, 0x71, 0x78, 0x7f, 0x6a, 0x6d, 0x64, 0x63,
    0x3e, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2c, 0x2b, 0x06, 0x01, 0x08, 0x0f, 0x1a, 0x1d, 0x14, 0x13,
    0xae, 0xa9, 0xa0, 0xa7, 0xb2, 0xb5, 0xbc, 0xbb, 0x96, 0x91, 0x98, 0x9f, 0x8a, 0x8d, 0x84, 0x83,
    0xde, 0xd9, 0xd0, 0xd7, 0xc2, 0xc5, 0xcc, 0xcb, 0xe6, 0xe1, 0xe8, 0xef, 0xfa, 0xfd, 0xf4, 0xf3
]


def crc8(data: bytes) -> int:
    """Calculate CRC8 checksum"""
    crc = 0
    for byte in data:
        crc = CRC8_TABLE[crc ^ byte]
    return crc


@dataclass
class RadioTelegram:
    """Represents an EnOcean radio telegram"""
    rorg: int
    data: bytes
    sender_id: int
    status: int
    dbm: int = 0

    @property
    def sender_hex(self) -> str:
        """Returns sender ID as hex string"""
        return f"0x{self.sender_id:08X}"

    @property
    def rorg_hex(self) -> str:
        """Returns RORG as hex string"""
        return f"{self.rorg:02X}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rorg": self.rorg_hex,
            "data": self.data.hex().upper(),
            "sender_id": self.sender_hex,
            "status": self.status,
            "dbm": self.dbm
        }


class SerialHandler:
    """Handles EnOcean serial/TCP communication

    Uses a dedicated thread for blocking serial I/O to prevent
    blocking the asyncio event loop.
    """

    def __init__(
        self,
        port: str,
        device_manager=None,
        mqtt_handler=None,
        eep_manager=None,
        telegram_buffer=None
    ):
        self.port = port
        self.device_manager = device_manager
        self.mqtt_handler = mqtt_handler
        self.eep_manager = eep_manager
        self.telegram_buffer = telegram_buffer

        self._serial: Optional[serial.Serial] = None
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._running = False
        self._read_task: Optional[asyncio.Task] = None
        self._telegram_callbacks: List[Callable] = []
        self._teach_in_callback: Optional[Callable] = None
        self._base_id: Optional[int] = None
        self._response_future: Optional[asyncio.Future] = None
        # Serializes _send_command() so concurrent callers don't clobber
        # each other's _response_future slot.
        self._cmd_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Returns connection status"""
        return self._connected

    @property
    def is_tcp(self) -> bool:
        """Returns True if using TCP connection"""
        return self.port.startswith("tcp:")

    async def connect(self):
        """Connect to EnOcean transceiver"""
        try:
            if self.is_tcp:
                await self._connect_tcp()
            else:
                await self._connect_serial()

            self._connected = True
            self._running = True

            # Start async read loop (uses run_in_executor for blocking serial reads)
            self._read_task = asyncio.create_task(self._read_loop())

            logger.info(f"Connected to EnOcean transceiver at {self.port}")

            # Read base ID from transceiver (needed for sending teach-in)
            await asyncio.sleep(0.5)  # Give read loop time to start
            base = await self.read_base_id()
            if base:
                logger.info(f"Transceiver Base ID: {base}")
            else:
                logger.warning("Could not read transceiver base ID")

        except Exception as e:
            logger.error(f"Failed to connect to EnOcean transceiver: {e}")
            raise

    async def _connect_serial(self):
        """Connect via serial port"""
        self._serial = serial.Serial(
            port=self.port,
            baudrate=57600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0
        )
        logger.info(f"Serial port opened: {self.port} @ 57600 baud (8N1)")

    async def _connect_tcp(self):
        """Connect via TCP with keepalive enabled.

        Without TCP keepalive, half-open connections (ESP32 crash, WiFi drop,
        router reboot — anything that prevents a clean FIN) are only detected
        after the OS default of ~2 hours. Tuning KEEPIDLE/INTVL/CNT brings
        that down to ~60s so the read loop can trigger a reconnect.
        """
        parts = self.port.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid TCP port format: {self.port}")

        host = parts[1]
        port = int(parts[2])

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5.0)
        self._socket.connect((host, port))
        self._socket.settimeout(1.0)

        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # Linux-specific knobs (HA OS runs on Alpine Linux).
        for name, value in (("TCP_KEEPIDLE", 30), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 3)):
            opt = getattr(socket, name, None)
            if opt is not None:
                try:
                    self._socket.setsockopt(socket.IPPROTO_TCP, opt, value)
                except OSError as e:
                    logger.debug(f"Could not set {name}={value}: {e}")

        logger.info(f"TCP connected to {host}:{port} (keepalive 30s idle / 10s intvl / 3 probes)")

    async def disconnect(self):
        """Disconnect from EnOcean transceiver"""
        self._running = False

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        await self._close_transport()

        self._connected = False
        logger.info("Disconnected from EnOcean transceiver")

    async def _read_loop(self):
        """Main read loop using run_in_executor for blocking serial reads.

        Recovers from connection loss by closing the dead transport and
        retrying the connect with exponential backoff. Previously any
        ConnectionError/SerialException killed the task and left the addon
        in a zombie state — /health still reported connected, but no data
        flowed and nothing in the log said why.
        """
        loop = asyncio.get_event_loop()
        timeout_count = 0
        packet_count = 0
        backoff = 1.0

        logger.info("Listening for EnOcean telegrams...")

        while self._running:
            try:
                # Wait for sync byte (0x55) using run_in_executor
                byte = await loop.run_in_executor(None, self._serial_read, 1)

                if not byte:
                    timeout_count += 1
                    if timeout_count % 30 == 0:
                        logger.info(f"Serial reader: still waiting for data ({timeout_count}s elapsed, {packet_count} packets so far)")
                    continue

                timeout_count = 0
                backoff = 1.0  # reset backoff on any successful read

                if byte[0] != SYNC_BYTE:
                    logger.debug(f"Non-sync byte: 0x{byte[0]:02X}")
                    continue

                logger.debug("Found sync byte 0x55")

                # Read header (4 bytes: data_len_hi, data_len_lo, optional_len, packet_type)
                header = await loop.run_in_executor(None, self._serial_read, 4)
                if len(header) != 4:
                    logger.warning("Incomplete header received")
                    continue

                data_len = (header[0] << 8) | header[1]
                optional_len = header[2]
                packet_type = header[3]

                # Read header CRC
                header_crc_byte = await loop.run_in_executor(None, self._serial_read, 1)
                if len(header_crc_byte) != 1:
                    logger.warning("Incomplete header CRC")
                    continue

                # Verify header CRC
                if crc8(header) != header_crc_byte[0]:
                    logger.debug("Invalid header CRC")
                    continue

                # Read data + optional data + data CRC
                total_data_len = data_len + optional_len + 1
                data_block = await loop.run_in_executor(None, self._serial_read, total_data_len)
                if len(data_block) != total_data_len:
                    logger.warning(f"Incomplete data block: {len(data_block)}/{total_data_len}")
                    continue

                # Split into parts
                packet_data = data_block[:data_len]
                optional_data = data_block[data_len:data_len + optional_len]
                data_crc = data_block[-1]

                # Verify data CRC
                if crc8(packet_data + optional_data) != data_crc:
                    logger.debug("Invalid data CRC")
                    continue

                packet_count += 1
                logger.debug(f"ESP3 packet #{packet_count}: type={packet_type:#04x} data_len={data_len} opt_len={optional_len}")

                # Process by packet type
                if packet_type == PACKET_TYPE_RADIO:
                    await self._process_radio_telegram(packet_data, optional_data)
                elif packet_type == PACKET_TYPE_RESPONSE:
                    logger.debug(f"Response packet: {packet_data.hex()}")
                    if self._response_future and not self._response_future.done():
                        self._response_future.set_result(packet_data)
                elif packet_type == PACKET_TYPE_EVENT:
                    logger.info(f"Event packet: {packet_data.hex()}")

            except asyncio.CancelledError:
                break
            except (ConnectionError, serial.SerialException, OSError) as e:
                if not self._running:
                    break
                logger.warning(f"Transport lost: {e} — reconnecting in {backoff:.0f}s")
                self._connected = False
                await self._close_transport()
                if not await self._wait_and_reconnect(backoff):
                    backoff = min(backoff * 2, 30.0)
                else:
                    backoff = 1.0
                timeout_count = 0
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Error in read loop: {e}", exc_info=True)
                    await asyncio.sleep(1)

        logger.info("Serial read loop stopped")

    async def _close_transport(self):
        """Close the current serial/socket transport without touching task state."""
        if self._serial:
            try:
                self._serial.close()
            except Exception as e:
                logger.debug(f"Error closing serial: {e}")
            self._serial = None
        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")
            self._socket = None

    async def _wait_and_reconnect(self, delay: float) -> bool:
        """Sleep `delay` seconds, then try to re-open the transport.

        Cancel any pending command future so callers don't hang. Returns
        True on success, False on failure (caller should grow backoff).
        """
        if self._response_future and not self._response_future.done():
            self._response_future.set_exception(ConnectionError("Transport lost"))

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise

        if not self._running:
            return False

        try:
            if self.is_tcp:
                await self._connect_tcp()
            else:
                await self._connect_serial()
            self._connected = True
            logger.info(f"Reconnected to EnOcean transceiver at {self.port}")
            # Re-read base ID in a separate task — we're still running inside
            # _read_loop, and _send_command() waits on _response_future which
            # only _read_loop can deliver. Awaiting it here deadlocks until
            # the command times out (3s). Firing it as a task lets the read
            # loop resume first, then the base-ID exchange runs concurrently.
            if self.is_tcp or self._base_id is None:
                asyncio.create_task(self._refresh_base_id_after_reconnect())
            return True
        except Exception as e:
            logger.error(f"Reconnect attempt failed: {e}")
            return False

    async def _refresh_base_id_after_reconnect(self):
        """Re-read base ID shortly after a reconnect.

        Runs as an independent task so it doesn't block the read loop that
        must deliver the response packet.
        """
        await asyncio.sleep(0.5)
        if not self._connected or not self._running:
            return
        try:
            await self.read_base_id()
        except Exception as e:
            logger.debug(f"Base ID re-read after reconnect failed: {e}")

    def _serial_read(self, size: int) -> bytes:
        """Blocking serial/TCP read - called via run_in_executor.

        Returns b"" on timeout (normal — the read loop treats this as idle).
        Raises ConnectionError / serial.SerialException on real failure so the
        read loop can trigger a reconnect. The previous version swallowed
        peer-closed (FIN -> recv returns b"") as "timeout", leaving the loop
        spinning forever with no log — exactly the silent-disconnect symptom.
        """
        if self.is_tcp:
            if not self._socket:
                raise ConnectionError("TCP socket not open")
            try:
                data = b""
                while len(data) < size:
                    chunk = self._socket.recv(size - len(data))
                    if not chunk:
                        raise ConnectionResetError("TCP peer closed connection (FIN received)")
                    data += chunk
                return data
            except socket.timeout:
                return b""

        if self._serial and self._serial.is_open:
            return self._serial.read(size)

        raise ConnectionError("No transport available")

    async def _process_radio_telegram(self, data: bytes, optional: bytes):
        """Process a received radio telegram"""
        if len(data) < 6:
            return

        rorg = data[0]

        # Extract sender ID (last 4 bytes before status)
        sender_id = int.from_bytes(data[-5:-1], 'big')
        status = data[-1]

        # Extract actual data (between RORG and sender ID)
        payload = data[1:-5]

        # Get signal strength from optional data
        # ESP3: optional[4] = dBm value (negated). 0xFF = not available (USB300).
        # Valid EnOcean RSSI: roughly -20 to -120 dBm.
        dbm = 0
        if len(optional) >= 5:
            raw_dbm = optional[4]
            if 20 <= raw_dbm <= 120:
                dbm = -raw_dbm
            # else: 0 = not available (0xFF, 0x00, or out-of-range)

        telegram = RadioTelegram(
            rorg=rorg,
            data=payload,
            sender_id=sender_id,
            status=status,
            dbm=dbm
        )

        logger.debug(f"RX [{telegram.sender_hex}] RORG={telegram.rorg_hex} Data={telegram.data.hex().upper()} dBm={telegram.dbm}")

        # Check if this is a teach-in telegram.
        # Only treat as teach-in if the sender is NOT already configured —
        # some non-standard devices (e.g. Eltako Staufix boiler sensor) send
        # data packets with LRN=0 in data[3], which the A5 check would
        # otherwise mis-flag as a teach-in on every single telegram.
        already_configured = (
            self.device_manager is not None
            and self.device_manager.get_device_by_address(telegram.sender_hex) is not None
        )
        is_teach_in = False if already_configured else self._is_teach_in(telegram)
        if is_teach_in:
            await self._handle_teach_in(telegram)

        # Find matching device and process
        device_name, eep_id, decoded = await self._process_telegram(telegram)

        # Store in telegram buffer
        if self.telegram_buffer:
            self.telegram_buffer.add(
                sender_id=telegram.sender_hex,
                rorg=telegram.rorg_hex,
                data=telegram.data.hex().upper(),
                status=telegram.status,
                dbm=telegram.dbm,
                device_name=device_name,
                eep_id=eep_id,
                decoded=decoded,
                is_teach_in=is_teach_in
            )

        # Call registered callbacks
        for callback in self._telegram_callbacks:
            try:
                await callback(telegram)
            except Exception as e:
                logger.error(f"Telegram callback error: {e}")

    def _is_teach_in(self, telegram: RadioTelegram) -> bool:
        """Check if telegram is a teach-in"""
        if telegram.rorg == 0xF6:
            # RPS has no teach-in
            return False
        elif telegram.rorg == 0xD5:
            # 1BS - check LRN bit
            if telegram.data:
                return (telegram.data[0] & 0x08) == 0
        elif telegram.rorg == 0xA5:
            # 4BS - check LRN bit
            if len(telegram.data) >= 4:
                return (telegram.data[3] & 0x08) == 0
        elif telegram.rorg == 0xD2:
            # VLD - check for teach-in variant
            return False  # VLD teach-in is more complex

        return False

    async def _handle_teach_in(self, telegram: RadioTelegram):
        """Handle teach-in telegram"""
        logger.info(f"TEACH-IN [{telegram.sender_hex}] RORG={telegram.rorg_hex} - New device wants to pair!")

        # Extract EEP from teach-in data
        func = 0
        type_ = 0

        if telegram.rorg == 0xA5 and len(telegram.data) >= 4:
            # 4BS teach-in with EEP
            func = (telegram.data[0] >> 2) & 0x3F
            type_ = ((telegram.data[0] & 0x03) << 5) | ((telegram.data[1] >> 3) & 0x1F)

        if self._teach_in_callback:
            await self._teach_in_callback({
                "sender_id": telegram.sender_hex,
                "rorg": telegram.rorg_hex,
                "func": f"{func:02X}",
                "type": f"{type_:02X}",
                "dbm": telegram.dbm
            })

    async def _process_telegram(self, telegram: RadioTelegram):
        """Process telegram and publish to MQTT

        Returns: (device_name, eep_id, decoded) or (None, None, None) if unknown device
        """
        if not self.device_manager:
            return None, None, None

        # Find device by address
        device = self.device_manager.get_device_by_address(telegram.sender_hex)
        if not device:
            logger.info(f"RX [{telegram.sender_hex}] Unknown device (not configured)")
            return None, None, None

        # Get EEP profile
        if not self.eep_manager:
            return device.name, device.eep_id, None

        profile = self.eep_manager.get_profile(device.eep_id)
        if not profile:
            logger.warning(f"Unknown EEP profile: {device.eep_id}")
            return device.name, device.eep_id, None

        # Check RORG matches the EEP profile — FD62NPN sends F6+A5+D1 but
        # only A5 matches A5-38-08. Decoding F6/D1 with A5 profile = garbage.
        try:
            expected_rorg = int(profile.rorg, 16)
            if telegram.rorg != expected_rorg:
                logger.debug(f"RX [{telegram.sender_hex}] RORG mismatch: got 0x{telegram.rorg:02X}, expected 0x{expected_rorg:02X} for {device.eep_id} — skipping decode")
                return device.name, device.eep_id, None
        except (ValueError, AttributeError):
            pass  # If RORG can't be parsed, proceed with decode anyway

        # Decode telegram using EEP profile
        decoded = self._decode_telegram(telegram, profile)

        # For light actuators, add HA-compatible state and brightness fields
        if device.actuator_type == "light":
            sw = decoded.get("SW", 0)
            edim = decoded.get("EDIM", 0)
            decoded["state"] = "ON" if sw else "OFF"
            # EDIM: Eltako dimmers report 0-100 as percentage regardless of
            # EDIMR flag (Eltako quirk: sends EDIMR=0 but uses 0-100 range).
            # Treat EDIM as 0-100 directly (matches brightness_scale: 100).
            decoded["brightness"] = round(min(float(edim), 100)) if edim else 0
            logger.debug(f"Light state: SW={sw}, EDIM={edim}, brightness={decoded['brightness']}%")

        logger.debug(f"RX [{telegram.sender_hex}] Device={device.name} EEP={device.eep_id} Decoded={decoded}")

        # Publish to MQTT
        if self.mqtt_handler:
            await self.mqtt_handler.publish_state(device.name, decoded)
            logger.debug(f"TX MQTT [{device.name}] Published state to {self.mqtt_handler.prefix}/{device.name}/state")

        return device.name, device.eep_id, decoded

    def _decode_telegram(self, telegram: RadioTelegram, profile) -> Dict[str, Any]:
        """Decode telegram data using EEP profile"""
        from datetime import datetime, timezone

        decoded = {
            "sender_id": telegram.sender_hex,
            "rssi": telegram.dbm,
            "last_seen": datetime.now(timezone.utc).isoformat()
        }

        if not profile.fields:
            # No field definitions - return raw data
            decoded["raw"] = telegram.data.hex().upper()
            return decoded

        # Decode each field
        data_int = int.from_bytes(telegram.data, 'big')
        data_bits = len(telegram.data) * 8

        for field in profile.fields:
            shortcut = field.get("shortcut", "")
            offset = field.get("offset", 0)
            size = field.get("size", 8)
            field_type = field.get("type", "value")

            # Extract bits
            shift = data_bits - offset - size
            if shift < 0:
                continue
            mask = (1 << size) - 1
            raw_value = (data_int >> shift) & mask

            # Decode based on type
            if field_type == "enum":
                # Find matching enum value
                values = field.get("values", [])
                decoded[shortcut] = raw_value
                for v in values:
                    if str(v.get("value")) == str(raw_value):
                        decoded[f"{shortcut}_text"] = v.get("description", "")
                        break

            elif field_type == "value":
                # Scale value
                scale_min = field.get("scale_min", 0)
                scale_max = field.get("scale_max", 255)
                range_min = field.get("min", 0)
                range_max = field.get("max", 255)

                if range_max != range_min:
                    scaled = scale_min + (raw_value - range_min) * (scale_max - scale_min) / (range_max - range_min)
                    decoded[shortcut] = round(scaled, 2)
                else:
                    decoded[shortcut] = raw_value

            else:
                decoded[shortcut] = raw_value

        # RPS (F6) rocker switches: when Energy Bow is released (EB=0),
        # the rocker fields (R1, R2) contain zeroed data which maps to
        # "Button AI" — misleading in MQTT Explorer. Override to "released".
        if decoded.get("EB") == 0:
            for field_key in ("R1", "R2"):
                if f"{field_key}_text" in decoded:
                    decoded[f"{field_key}_text"] = "released"

        return decoded

    async def _write_packet(self, packet: bytes):
        """Write a raw packet to the transport without blocking the event loop.

        socket.send() and serial.write() are synchronous — calling them
        directly from an async handler can freeze the whole FastAPI app
        when the transport is slow or half-dead (full send buffer).
        """
        loop = asyncio.get_event_loop()
        if self._serial:
            await loop.run_in_executor(None, self._serial.write, packet)
        elif self._socket:
            # sendall() loops internally until all bytes are written or an
            # error is raised — safer than send() for the multi-byte packets
            # we emit here.
            await loop.run_in_executor(None, self._socket.sendall, packet)
        else:
            raise ConnectionError("No transport available")

    async def _send_command(self, command_code: int) -> bytes:
        """Send an ESP3 common command and wait for response.

        Serialized via self._cmd_lock so concurrent callers don't overwrite
        each other's _response_future slot (the read loop only fills the
        currently-pending slot and would silently mis-route responses).

        Raises:
            NotConnectedError: transport is not open
            CommandTimeoutError: no response within 3s
            TransportLostError: transport died during the exchange
        """
        if not self._connected:
            raise NotConnectedError(f"Cannot send 0x{command_code:02X}: transceiver not connected")

        packet_data = bytes([command_code])
        header = bytes([0x00, len(packet_data), 0x00, PACKET_TYPE_COMMON_COMMAND])
        header_crc = crc8(header)
        data_crc = crc8(packet_data)
        packet = bytes([SYNC_BYTE]) + header + bytes([header_crc]) + packet_data + bytes([data_crc])

        async with self._cmd_lock:
            loop = asyncio.get_event_loop()
            self._response_future = loop.create_future()

            try:
                await self._write_packet(packet)
                return await asyncio.wait_for(self._response_future, timeout=3.0)
            except asyncio.TimeoutError:
                raise CommandTimeoutError(f"No response to command 0x{command_code:02X} after 3s")
            except (ConnectionError, serial.SerialException, OSError) as e:
                self._connected = False
                raise TransportLostError(f"Transport lost sending 0x{command_code:02X}: {e}") from e
            finally:
                self._response_future = None

    async def read_base_id(self) -> Optional[str]:
        """Read the base ID from the USB300 transceiver.

        Returns base ID as hex string (e.g., '0xFFE30180') or None on error.
        Logs the specific reason (not-connected / timeout / transport-lost)
        so callers can tell why it failed by reading the log.
        """
        try:
            response = await self._send_command(CO_RD_IDBASE)
        except NotConnectedError as e:
            logger.warning(f"Base ID read skipped: {e}")
            return None
        except CommandTimeoutError as e:
            logger.error(f"Base ID read timed out: {e}")
            return None
        except TransportLostError as e:
            logger.error(f"Base ID read failed (transport lost): {e}")
            return None

        if not response or len(response) < 5:
            logger.error(f"Invalid base ID response: {response}")
            return None

        return_code = response[0]
        if return_code != 0x00:
            logger.error(f"Base ID read failed with code: {return_code:#04x}")
            return None

        base_id = int.from_bytes(response[1:5], 'big')
        self._base_id = base_id
        logger.info(f"USB300 Base ID: 0x{base_id:08X}")
        return f"0x{base_id:08X}"

    @property
    def base_id(self) -> Optional[str]:
        """Return cached base ID as hex string"""
        if self._base_id is None:
            return None
        return f"0x{self._base_id:08X}"

    def get_sender_id(self, offset: int = 1) -> Optional[int]:
        """Get a sender ID derived from base ID + offset (1-127)"""
        if self._base_id is None:
            return None
        if not 1 <= offset <= 127:
            return None
        return self._base_id + offset

    async def send_f6_teach_in(self, destination: int, sender_offset: int = 1) -> bool:
        """Send F6 (RPS) teach-in sequence to an Eltako actuator.

        Sends a rocker switch press + release to teach-in the sender ID.
        The actuator must be in learn mode.

        Args:
            destination: Target actuator address (int)
            sender_offset: Offset from base ID for sender (1-127)

        Returns True if telegrams were sent successfully.
        """
        sender_id = self.get_sender_id(sender_offset)
        if sender_id is None:
            logger.error("Cannot send teach-in: base ID not read yet")
            return False

        logger.info(f"Sending F6 teach-in to 0x{destination:08X} with sender 0x{sender_id:08X} (broadcast)")

        # Teach-in uses BROADCAST (0xFFFFFFFF) like real EnOcean pushbuttons.
        # Eltako actuators in learn mode listen for broadcast F6 telegrams
        # and store the sender ID from the telegram.
        broadcast = 0xFFFFFFFF

        # Send button press (BI): data=0x50, status=0x30 (T21+NU)
        success = await self.send_telegram(
            sender_id=sender_id,
            rorg=0xF6,
            data=bytes([0x50]),
            destination=broadcast
        )
        if not success:
            return False

        await asyncio.sleep(0.3)

        # Send button release: data=0x00, status=0x20 (T21, no NU)
        success = await self.send_telegram(
            sender_id=sender_id,
            rorg=0xF6,
            data=bytes([0x00]),
            destination=broadcast,
            status=0x20
        )
        return success

    async def send_a5_teach_in(self, destination: int, sender_offset: int = 1) -> bool:
        """Send A5-38-08 teach-in for Eltako dimmers (FD62NPN, FUD61).

        Uses the proven two-step sequence from kipe/enocean #130:
        1. Pre-teach data telegram (wakes up the actuator)
        2. Wait 3 seconds
        3. Actual teach-in telegram (LRN bit = 0)

        Then also sends F6 rocker press as fallback.
        The actuator must be in learn mode (30s window).
        """
        sender_id = self.get_sender_id(sender_offset)
        if sender_id is None:
            logger.error("Cannot send teach-in: base ID not read yet")
            return False

        broadcast = 0xFFFFFFFF
        logger.info(f"=== DIMMER TEACH-IN === sender=0x{sender_id:08X}, dest=0x{destination:08X}")

        # Step 1: Pre-teach data telegram (proven kipe/enocean #130 sequence)
        # DB0=0x28: bit3=1 (data, not teach-in), bit5=1 — "wakes up" the actuator
        pre_teach = bytes([0x00, 0x00, 0x00, 0x28])
        logger.info("  [1/3] A5 pre-teach telegram: 00000028 (broadcast)")
        await self.send_telegram(
            sender_id=sender_id, rorg=0xA5,
            data=pre_teach, destination=broadcast, status=0x30
        )

        # Wait 3 seconds (important: actuator needs time to process)
        await asyncio.sleep(3.0)

        # Step 2: A5 teach-in telegram (LRN bit = 0)
        # E0400D80: standard 4BS teach-in with LRN type=0 (sender-only)
        teach_in = bytes([0xE0, 0x40, 0x0D, 0x80])
        logger.info("  [2/3] A5 teach-in telegram: E0400D80 (broadcast)")
        await self.send_telegram(
            sender_id=sender_id, rorg=0xA5,
            data=teach_in, destination=broadcast, status=0x30
        )

        await asyncio.sleep(1.0)

        # Step 3: F6 rocker press as fallback (what real pushbuttons send)
        # Some Eltako dimmers prefer F6 over A5 for teach-in
        logger.info("  [3/3] F6 Rocker BI press+release (broadcast)")
        await self.send_telegram(
            sender_id=sender_id, rorg=0xF6,
            data=bytes([0x50]), destination=broadcast, status=0x30
        )
        await asyncio.sleep(0.3)
        await self.send_telegram(
            sender_id=sender_id, rorg=0xF6,
            data=bytes([0x00]), destination=broadcast, status=0x20
        )

        logger.info("=== DIMMER TEACH-IN COMPLETE === (3 steps, 4 telegrams)")
        return True

    async def send_a5_dimmer_command(self, sender_id: int, command: str,
                                     dim_value: int = 255, ramp_time: int = 1) -> bool:
        """Send A5-38-08 Central Command Dimming telegram.

        Args:
            sender_id: Sender ID (already resolved integer)
            command: "ON", "OFF", or "DIM"
            dim_value: Brightness 0-255 (for ON/DIM)
            ramp_time: Ramp time in seconds (0=default, 1-255)

        Returns True if telegram was sent successfully.
        """
        # A5-38-08 Command 2 (Dimming):
        # DB3 = 0x02 (command ID = dimming)
        # DB2 = dim value (0x00-0xFF)
        # DB1 = ramp time (seconds)
        # DB0 = flags: bit3=LRN(1=data), bit2=store, bit1=dim_mode(0=stored,1=use DB2), bit0=SW(on/off)
        if command == "OFF":
            # 0x08: LRN=1, store=0, dim_mode=0, SW=0 (off)
            data = bytes([0x02, 0x00, ramp_time & 0xFF, 0x08])
        elif command == "ON":
            # 0x09: LRN=1, store=0, dim_mode=0 (use stored brightness), SW=1 (on)
            data = bytes([0x02, 0x00, ramp_time & 0xFF, 0x09])
        else:  # DIM - set specific brightness
            # 0x0B: LRN=1, store=0, dim_mode=1 (use DB2 value), SW=1 (on)
            val = max(0, min(255, dim_value))
            data = bytes([0x02, val, ramp_time & 0xFF, 0x0B])

        logger.info(f"Sending A5-38-08 dimmer {command} (value={dim_value}, ramp={ramp_time}s) sender=0x{sender_id:08X}")

        success = await self.send_telegram(
            sender_id=sender_id,
            rorg=0xA5,
            data=data,
            destination=0xFFFFFFFF  # broadcast
        )
        return success

    def register_telegram_callback(self, callback: Callable):
        """Register callback for received telegrams"""
        self._telegram_callbacks.append(callback)

    def set_teach_in_callback(self, callback: Callable):
        """Set callback for teach-in events"""
        self._teach_in_callback = callback

    async def send_telegram(self, sender_id: int, rorg: int, data: bytes, destination: int = 0xFFFFFFFF, status: int = None):
        """Send an EnOcean telegram"""
        if not self._connected:
            logger.error("Cannot send - not connected")
            return False

        # Build radio telegram
        # RORG + data + sender_id (4 bytes) + status (1 byte)
        sender_bytes = sender_id.to_bytes(4, 'big')
        if status is None:
            # F6 (RPS) needs T21 flag (0x30 for pressed, 0x20 for released)
            status = 0x30 if (rorg == 0xF6 and data and data[0] != 0x00) else 0x00

        packet_data = bytes([rorg]) + data + sender_bytes + bytes([status])

        # Optional data: SubTelNum, DestinationID, dBm, SecurityLevel
        dest_bytes = destination.to_bytes(4, 'big')
        optional = bytes([0x03]) + dest_bytes + bytes([0xFF, 0x00])

        # Build ESP3 packet
        data_len = len(packet_data)
        optional_len = len(optional)

        header = bytes([
            (data_len >> 8) & 0xFF,
            data_len & 0xFF,
            optional_len,
            PACKET_TYPE_RADIO
        ])

        header_crc = crc8(header)
        data_crc = crc8(packet_data + optional)

        packet = bytes([SYNC_BYTE]) + header + bytes([header_crc]) + packet_data + optional + bytes([data_crc])

        try:
            await self._write_packet(packet)
            logger.debug(f"TX EnOcean: RORG={rorg:02X}, Data={data.hex()}, Dest={destination:08X}")
            return True
        except (ConnectionError, serial.SerialException, OSError) as e:
            logger.error(f"Transport error sending telegram: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to send telegram: {e}")
            return False
