"""
Serial Handler - Handles EnOcean serial/TCP communication
Based on ESP3 protocol

Uses a dedicated thread for serial I/O to avoid blocking the asyncio event loop.
"""

import os
import time
import logging
import asyncio
import serial
import socket
from contextlib import asynccontextmanager
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

# Response return codes
RET_OK = 0x00

# Transmit pacing. The transceiver has one radio and a small transmit queue,
# and its response packets carry no sequence number. Only one ESP3 request may
# therefore be in flight, and consecutive telegrams need a gap or the module
# silently drops what does not fit. See ADR-0012.
TX_GAP_SECONDS = 0.04
TX_SLOT_TIMEOUT = 1.0
TX_WRITE_TIMEOUT = 0.5
TX_RESPONSE_TIMEOUT = 0.3
COMMAND_RESPONSE_TIMEOUT = 1.0

# An F6 rocker press is terminated by a release, and the interval between the
# two *is* the command: Eltako actuators read a short press as "run the full
# way" and a long one as "move only while held". A shutter whose press got
# stretched travels a few centimetres instead of closing. 100 ms is the short
# press we simulate, 250 ms the point where the meaning starts to shift.
RPS_HOLD_SECONDS = 0.1
RPS_HOLD_WARN_SECONDS = 0.25


class TransceiverError(Exception):
    """Base class for EnOcean transceiver command failures."""


class NotConnectedError(TransceiverError):
    """Raised when a command is attempted with no active transport."""


class CommandTimeoutError(TransceiverError):
    """Raised when a command was sent but no response arrived in time."""


class TransportLostError(TransceiverError):
    """Raised when the transport died while a command was in flight."""


class TransceiverBusyError(TransceiverError):
    """Raised when the transmit slot could not be acquired in time.

    Means an earlier request is still occupying the transceiver, normally a
    stalled write on a half-dead transport.
    """


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


def _radio_log_line(rorg: int, data: bytes, destination: int) -> str:
    """The one debug line per outgoing telegram, unchanged since beta6 so the
    field logs people paste stay comparable."""
    return f"TX EnOcean: RORG={rorg:02X}, Data={data.hex()}, Dest={destination:08X}"


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
        # UTE (RORG D4) auto-response sender offset. NodOn D2-05-00 covers in
        # bidirectional learn mode expect a UTE teach-in *response* carrying the
        # controller Sender ID they must bind to (base_id + offset). Commands
        # are addressed (destination = actuator), so one gateway sender can
        # drive many covers, a single offset is fine. Set per teach-in session.
        self._ute_response_offset: int = 1
        self._base_id: Optional[int] = None
        self._response_future: Optional[asyncio.Future] = None
        # Guards every conversation with the transceiver, radio telegrams and
        # common commands alike: one request in flight at a time, so nothing
        # clobbers the _response_future slot and nothing overruns the module's
        # transmit queue. _last_tx carries the gap across slots.
        self._tx_lock = asyncio.Lock()
        self._last_tx: float = 0.0

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
        router reboot, anything that prevents a clean FIN) are only detected
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
        in a zombie state, /health still reported connected, but no data
        flowed and nothing in the log said why.
        """
        loop = asyncio.get_event_loop()
        timeout_count = 0
        packet_count = 0
        backoff = 1.0
        skipped_bytes = 0
        skipped_sample = b""

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
                    # One line per discarded byte floods the log at debug level
                    # exactly when debug is needed: a gateway that emits a few
                    # stray bytes per packet produces a steady stream of these
                    # and pushes the actual telegrams out of the add-on's log
                    # buffer. Count them and report on resync instead, which
                    # keeps the diagnostic (how much noise, and what it was)
                    # without burying everything else.
                    skipped_bytes += 1
                    if len(skipped_sample) < 24:
                        skipped_sample += byte
                    if skipped_bytes % 1000 == 0:
                        logger.debug(f"Still hunting for sync: {skipped_bytes} bytes discarded, starts {skipped_sample.hex().upper()}")
                    continue

                if skipped_bytes:
                    logger.debug(f"Found sync byte 0x55 after discarding {skipped_bytes} byte(s), starts {skipped_sample.hex().upper()}")
                    skipped_bytes = 0
                    skipped_sample = b""
                else:
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
                logger.warning(f"Transport lost: {e}, reconnecting in {backoff:.0f}s")
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
            # Re-read base ID in a separate task, we're still running inside
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

        Returns b"" on timeout (normal, the read loop treats this as idle).
        Raises ConnectionError / serial.SerialException on real failure so the
        read loop can trigger a reconnect. The previous version swallowed
        peer-closed (FIN -> recv returns b"") as "timeout", leaving the loop
        spinning forever with no log, exactly the silent-disconnect symptom.
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
        # Only treat as teach-in if the sender is NOT already configured:
        # some non-standard devices (e.g. Eltako Staufix boiler sensor) send
        # data packets with LRN=0 in data[3], which the A5 check would
        # otherwise mis-flag as a teach-in on every single telegram.
        already_configured = (
            self.device_manager is not None
            and self.device_manager.get_device_by_address(telegram.sender_hex) is not None
        )
        if telegram.rorg == 0xD4:
            # UTE (RORG 0xD4) teach-in queries, e.g. NodOn D2-05-00 in
            # bidirectional learn mode, must be answered with a UTE response
            # to complete pairing. This is handled independently of
            # `already_configured` (re-pairing a known device must work too),
            # but only while a teach-in session is active so stray UTE traffic
            # from neighbouring modules is ignored.
            is_teach_in = self._is_ute_teach_in_query(telegram)
            if is_teach_in and self._teach_in_callback is not None:
                await self._handle_ute_teach_in(telegram)
        else:
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

    def _is_ute_teach_in_query(self, telegram: RadioTelegram) -> bool:
        """True if telegram is a UTE (RORG 0xD4) EEP teach-in *query*.

        UTE query layout (7 data bytes, DB6..DB0):
            DB6: bit7 uni(0)/bidirectional(1), bit6 response expected(0)/not(1),
                 bits5-4 request type, bits3-0 command id (0x0 = teach-in query)
        We only treat command id 0x0 as an inbound query to answer; our own
        responses use command id 0x1 and must not be re-processed.
        """
        if telegram.rorg != 0xD4 or len(telegram.data) < 7:
            return False
        return (telegram.data[0] & 0x0F) == 0x0

    async def _handle_ute_teach_in(self, telegram: RadioTelegram):
        """Parse a UTE teach-in query and answer it so the module pairs.

        UTE query DB6..DB0 (data[0..6]):
            DB6 = command/flags (see _is_ute_teach_in_query)
            DB5 = number of channels
            DB4 = manufacturer ID LSB
            DB3 = bits2-0 manufacturer ID MSB (rest reserved)
            DB2 = EEP TYPE, DB1 = EEP FUNC, DB0 = EEP RORG
        """
        d = telegram.data
        db6 = d[0]
        bidirectional = bool(db6 & 0x80)
        response_expected = (db6 & 0x40) == 0   # bit6 = 0 -> response expected
        channels = d[1]
        manuf = ((d[3] & 0x07) << 8) | d[2]
        eep_type, eep_func, eep_rorg = d[4], d[5], d[6]

        logger.info(
            f"UTE TEACH-IN [{telegram.sender_hex}] "
            f"EEP={eep_rorg:02X}-{eep_func:02X}-{eep_type:02X} manuf=0x{manuf:03X} "
            f"channels={channels} bidir={bidirectional} resp_expected={response_expected}"
        )

        response_sender = self.get_sender_id(self._ute_response_offset)

        # Only bidirectional queries that expect a response get answered; a
        # unidirectional module just wants us to remember its EEP.
        if bidirectional and response_expected:
            if response_sender is None:
                logger.warning("UTE teach-in: base ID not read yet, cannot send response")
            else:
                await self.send_ute_response(
                    destination=telegram.sender_id,
                    response_sender=response_sender,
                    query_data=d,
                )

        if self._teach_in_callback:
            await self._teach_in_callback({
                "sender_id": telegram.sender_hex,
                "rorg": f"0x{eep_rorg:02X}",
                "func": f"{eep_func:02X}",
                "type": f"{eep_type:02X}",
                "dbm": telegram.dbm,
                "teach_method": "UTE",
                # Number of I/O channels the module reports (DB5). 2-channel
                # modules (e.g. NodOn SIN-2-2-01) can send a follow-up telegram
                # selecting the target channel, so the UI waits for it (#24).
                "channels": channels,
                # Sender ID the module was told to bind, the new device MUST be
                # configured with exactly this value for commands to reach it.
                "response_sender": f"0x{response_sender:08X}" if response_sender else None,
            })

    async def send_ute_response(self, destination: int, response_sender: int,
                                query_data: bytes) -> bool:
        """Send a UTE (RORG 0xD4) EEP teach-in *response* accepting the pairing.

        Byte layout follows the python-enocean reference (UTETeachInPacket):
            DB6 = 0x91  bit7=1 bidirectional, bits5-4=01 "request accepted,
                        teach-in successful", bits3-0=0001 command = response
            DB5..DB0 = echoed unchanged from the query (channels, manufacturer,
                       EEP TYPE/FUNC/RORG) so the module confirms the same EEP.
        The telegram is *addressed* back to the requesting module, and its
        sender field carries the controller Sender ID the module binds to.
        """
        # DB6: 1001 0001 = accepted + teach-in response (command id 1)
        db6 = 0x91
        data = bytes([db6]) + bytes(query_data[1:7])  # DB6 + echoed DB5..DB0

        logger.info(
            f"Sending UTE teach-in response (accepted) to 0x{destination:08X} "
            f"data={data.hex().upper()} sender=0x{response_sender:08X}"
        )
        return await self.send_telegram(
            sender_id=response_sender,
            rorg=0xD4,
            data=data,
            destination=destination,
            status=0x00,
        )

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

        # An RPS actuator confirms its own output with a plain rocker telegram
        # sent from its own address (Eltako FL62, FSR61 and friends). For those
        # modules the confirmation is the only state feedback there is, so it
        # is derived first, before either of the two paths that used to swallow
        # it can run:
        #   * the module may be taught in under a non-F6 EEP (Eltako's own
        #     tables point at A5-38-08), and the RORG guard below drops such a
        #     telegram undecoded,
        #   * the module may be configured as "light" instead of "switch", and
        #     the light branch only ever looked at A5-38-08 dimmer frames.
        # Either way the telegram still appeared in the device's telegram list
        # while the HA entity stayed "unknown" forever. Forum report on an
        # Eltako FL62NP.
        rps_state = self._rps_actuator_state(telegram, device)

        # The same holds for an Eltako shutter actuator, which confirms with a
        # rocker telegram (end position, travel started) and reports the time
        # it ran in a 4BS telegram. Both come from the actuator's own address
        # whatever EEP it is configured under, so they are read before the
        # RORG guard can drop them (issue #39, ADR-0014).
        cover_state = self._eltako_cover_state(telegram, device)
        cover_travel = self._eltako_cover_travel(telegram, device)

        # Check RORG matches the EEP profile, FD62NPN sends F6+A5+D1 but
        # only A5 matches A5-38-08. Decoding F6/D1 with A5 profile = garbage.
        try:
            expected_rorg = int(profile.rorg, 16)
        except (ValueError, AttributeError, TypeError):
            expected_rorg = telegram.rorg  # unparsable profile RORG: decode anyway

        if telegram.rorg == expected_rorg:
            # Decode telegram using EEP profile
            decoded = self._decode_telegram(telegram, profile)
        elif rps_state is not None or cover_state is not None or cover_travel is not None:
            # Confirmation of an actuator taught in under another EEP. No field
            # decode is possible here, but the state it reports is.
            decoded = self._telegram_meta(telegram)
            logger.debug(f"RX [{telegram.sender_hex}] RORG 0x{telegram.rorg:02X} does not match {device.eep_id}, taken as RPS actuator status only")
        else:
            logger.debug(f"RX [{telegram.sender_hex}] RORG mismatch: got 0x{telegram.rorg:02X}, expected 0x{expected_rorg:02X} for {device.eep_id}, skipping decode")
            return device.name, device.eep_id, None

        if cover_state is not None:
            decoded["state"] = cover_state
            logger.debug(f"Eltako cover status: {device.name} -> {cover_state}")
        elif cover_travel is not None:
            direction, seconds = cover_travel
            # The travel report is also the message that the motor has stopped.
            # Leaving "opening"/"closing" standing would show a shutter moving
            # forever, so a settled state is published even when the position
            # cannot be computed.
            decoded["state"] = "open"
            logger.debug(f"Eltako cover travel: {device.name} ran {seconds:.1f}s {direction}")

        if rps_state is not None:
            decoded["state"] = rps_state
            if device.actuator_type == "light":
                # An RPS light actuator switches, it does not dim. Report the
                # only two brightness values it can ever be in.
                decoded["brightness"] = 100 if rps_state == "ON" else 0
            logger.debug(f"RPS actuator status: {device.name} -> {rps_state}")

        # For light actuators, add HA-compatible state and brightness fields.
        # SW and EDIM come from A5-38-08, so this must not run for a D2-01
        # module configured as a light: SW would be missing and the light
        # would be reported permanently OFF. D2-01 is handled per target
        # below, because there the channel decides who the value belongs to.
        elif device.actuator_type == "light" and telegram.rorg == 0xA5:
            sw = decoded.get("SW", 0)
            edim = decoded.get("EDIM", 0)
            decoded["state"] = "ON" if sw else "OFF"
            # EDIM: Eltako dimmers report 0-100 as percentage regardless of
            # EDIMR flag (Eltako quirk: sends EDIMR=0 but uses 0-100 range).
            # Treat EDIM as 0-100 directly (matches brightness_scale: 100).
            decoded["brightness"] = round(min(float(edim), 100)) if edim else 0
            logger.debug(f"Light state: SW={sw}, EDIM={edim}, brightness={decoded['brightness']}%")

        logger.debug(f"RX [{telegram.sender_hex}] Device={device.name} EEP={device.eep_id} Decoded={decoded}")

        # Publish to MQTT, to EVERY device on this address. A 2-channel module
        # is configured once per output, all sharing the module address, so
        # publishing only to the first one left the second channel without any
        # state (#24).
        if self.mqtt_handler:
            targets = self.device_manager.get_devices_by_address(telegram.sender_hex) or [device]

            # A D2-01 module reports its output in an addressed status
            # telegram: IO carries the channel, OV the output value (0 = off,
            # 1..100 = on at that percentage). Both channels of a module share
            # one address, so the value belongs to exactly one configured
            # device and the mapping has to happen per target, not once for
            # the whole address. Without this the switch entity never followed
            # the module, only the echo of our own commands (ADR-0005).
            d2_01_status = (telegram.rorg == 0xD2
                            and str(device.eep_id).upper().startswith("D2-01")
                            and decoded.get("OV") is not None)

            for target in targets:
                payload = dict(decoded)
                if d2_01_status:
                    io = decoded.get("IO")
                    ch = int(getattr(target, "channel", 0) or 0)
                    if io is None or int(io) == ch:
                        ov = int(decoded.get("OV") or 0)
                        if target.actuator_type in ("light", "switch"):
                            payload["state"] = "ON" if ov else "OFF"
                            if target.actuator_type == "light":
                                payload["brightness"] = min(ov, 100)
                            logger.debug(f"D2-01 status: IO={io} OV={ov} -> {target.name} {payload['state']}")
                    else:
                        # Another channel's value. Leave this entity's state
                        # alone instead of overwriting it with a foreign one.
                        payload.pop("state", None)
                        payload.pop("brightness", None)
                if target.actuator_type == "cover" and (cover_state is not None
                                                        or cover_travel is not None):
                    # travel_time is per device, and so is the previous
                    # position the travel is measured against, so the position
                    # is resolved per target rather than once for the address.
                    pos = self._eltako_cover_position(target, cover_state, cover_travel)
                    if pos is None:
                        # Keep the last known position in the retained payload,
                        # dropping it would leave the slider empty after a
                        # restart.
                        prev = self.mqtt_handler.get_last_state(target.name) or {}
                        pos = prev.get("POS")
                    elif cover_travel is not None:
                        payload["state"] = "open" if pos > 0 else "closed"
                    if pos is not None:
                        payload["POS"] = pos

                if (target.actuator_type in ("light", "switch", "cover")
                        and payload.get("state") is None):
                    # A rocker release (and a foreign channel's report) carries
                    # no state. Publishing it as it is drops "state" from the
                    # retained topic, so the entity came back "unknown" after
                    # every Home Assistant restart. Repeat the last known value
                    # instead of erasing it.
                    prev = self.mqtt_handler.get_last_state(target.name) or {}
                    if prev.get("state") is not None:
                        payload["state"] = prev["state"]
                        if target.actuator_type == "light" and "brightness" in prev:
                            payload["brightness"] = prev["brightness"]

                await self.mqtt_handler.publish_state(target.name, payload)
                logger.debug(f"TX MQTT [{target.name}] Published state to {self.mqtt_handler.prefix}/{target.name}/state")

        return device.name, device.eep_id, decoded

    # R1, the first rocker action of an RPS telegram: 0 = AI, 1 = AO,
    # 2 = BI, 3 = BO. An actuator's status confirmation uses the OPPOSITE
    # convention to the rocker press we send as a command: Eltako confirms ON
    # with 0x70 (BO) and OFF with 0x50 (BI), while the command press for ON is
    # 0x50. Reported by salzrat on the community forum and confirmed against
    # Eltako's telegram documentation. Rocker A is read the same way, because
    # a module taught in on the A channel confirms with 0x30 (AO) / 0x10 (AI).
    # Actuators taught in the other way round are handled by the device's
    # "invert" option.
    _RPS_ON_BY_R1 = {0: False, 1: True, 2: False, 3: True}

    # An Eltako shutter actuator reports on its own, in two telegrams that have
    # nothing to do with the EEP it was taught in under. From Eltako's
    # "Inhalte der Eltako-Funktelegramme", section FJ62/12-36V DC, FJ62NP-230V:
    #   RPS (F6): DB3 0x01 = travel up started, 0x02 = travel down started,
    #             0x70 = upper end position, 0x50 = lower end position.
    #   4BS (A5): DB3+DB2 = the time it actually ran in 100 ms, DB1 = 0x01 ran
    #             up / 0x02 ran down, DB0 = 0x0A, or 0x0E while the actuator is
    #             blocked for pushbuttons.
    # The 4BS report is sent only when the run ended before the actuator's own
    # runtime expired, so the end positions are the only points where the
    # position is certain. They are the synchronisation points, which is how
    # Eltako's own GFVS software tracks the position. See ADR-0014.
    _ELTAKO_COVER_RPS = {0x70: "open", 0x50: "closed", 0x01: "opening", 0x02: "closing"}
    _ELTAKO_COVER_INVERTED = {"open": "closed", "closed": "open",
                              "opening": "closing", "closing": "opening"}

    def _eltako_cover_state(self, telegram: RadioTelegram, device) -> Optional[str]:
        """HA cover state if this RPS telegram is a shutter's own report."""
        if telegram.rorg != 0xF6 or not telegram.data:
            return None
        if getattr(device, "actuator_type", "") != "cover":
            return None

        state = self._ELTAKO_COVER_RPS.get(telegram.data[0])
        if state is None:
            return None
        if getattr(device, "invert", False):
            state = self._ELTAKO_COVER_INVERTED[state]
        return state

    def _eltako_cover_travel(self, telegram: RadioTelegram, device) -> Optional[tuple]:
        """(direction, seconds) if this 4BS telegram is a shutter's travel report."""
        if telegram.rorg != 0xA5 or len(telegram.data) != 4:
            return None
        if getattr(device, "actuator_type", "") != "cover":
            return None

        db0 = telegram.data[3]
        # bit3 = data telegram, bit1 = time given in 100 ms over DB3+DB2. A
        # travel *command* uses the seconds base instead, so this also keeps
        # the add-on from reading someone else's command as a report.
        if db0 & 0x0A != 0x0A:
            return None

        direction = {0x01: "opening", 0x02: "closing"}.get(telegram.data[2])
        if direction is None:
            return None
        if getattr(device, "invert", False):
            direction = self._ELTAKO_COVER_INVERTED[direction]

        seconds = ((telegram.data[0] << 8) | telegram.data[1]) / 10
        return direction, seconds

    def _eltako_cover_position(self, device, cover_state: Optional[str],
                               cover_travel: Optional[tuple]) -> Optional[int]:
        """Position in HA terms (100 = open) from an Eltako shutter's report.

        An end position is absolute and needs nothing else. A travel report is
        relative: it only becomes a position when it is measured against the
        configured full travel time, and only from a known previous position.
        Without either, None leaves the last position untouched rather than
        inventing one.
        """
        if cover_state in ("open", "closed"):
            return 100 if cover_state == "open" else 0
        if cover_travel is None:
            return None

        travel_time = int(getattr(device, "travel_time", 0) or 0)
        if travel_time <= 0 or not self.mqtt_handler:
            return None

        previous = (self.mqtt_handler.get_last_state(device.name) or {}).get("POS")
        if previous is None:
            return None

        direction, seconds = cover_travel
        step = seconds / travel_time * 100
        moved = float(previous) + (step if direction == "opening" else -step)
        return int(round(max(0.0, min(100.0, moved))))

    def _rps_actuator_state(self, telegram: RadioTelegram, device) -> Optional[str]:
        """"ON"/"OFF" if this telegram is an actuator's own status report."""
        if telegram.rorg != 0xF6 or not telegram.data:
            return None
        if getattr(device, "actuator_type", "") not in ("light", "switch"):
            return None

        db0 = telegram.data[0]
        if not db0 & 0x10:
            return None  # energy bow released: end of a press, not a status

        on = self._RPS_ON_BY_R1.get((db0 >> 5) & 0x07)
        if on is None:
            return None
        if getattr(device, "invert", False):
            on = not on
        return "ON" if on else "OFF"

    @staticmethod
    def _telegram_meta(telegram: RadioTelegram) -> Dict[str, Any]:
        """The fields every published state carries, whatever the EEP is."""
        from datetime import datetime, timezone

        return {
            "sender_id": telegram.sender_hex,
            "rssi": telegram.dbm,
            "last_seen": datetime.now(timezone.utc).isoformat()
        }

    def _decode_telegram(self, telegram: RadioTelegram, profile) -> Dict[str, Any]:
        """Decode telegram data using EEP profile"""
        decoded = self._telegram_meta(telegram)

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
        # "Button AI", misleading in MQTT Explorer. Override to "released".
        if decoded.get("EB") == 0:
            for field_key in ("R1", "R2"):
                if f"{field_key}_text" in decoded:
                    decoded[f"{field_key}_text"] = "released"

        return decoded

    @asynccontextmanager
    async def _tx_slot(self):
        """Hold the exclusive right to talk to the transceiver.

        Every write goes through here. Acquiring has a timeout so a stalled
        write on a half-dead transport cannot park the whole send path
        forever, the caller gets an error instead of hanging.
        """
        try:
            await asyncio.wait_for(self._tx_lock.acquire(), timeout=TX_SLOT_TIMEOUT)
        except asyncio.TimeoutError:
            raise TransceiverBusyError(
                f"Transceiver still busy after {TX_SLOT_TIMEOUT:.0f}s, request dropped"
            )
        try:
            yield
        finally:
            self._tx_lock.release()

    async def _write_packet(self, packet: bytes):
        """Write a raw packet to the transport, keeping the inter-telegram gap.

        Only call while holding _tx_slot(): the gap bookkeeping and the
        one-request-in-flight rule both depend on it.

        socket.send() and serial.write() are synchronous, calling them
        directly from an async handler can freeze the whole FastAPI app
        when the transport is slow or half-dead (full send buffer). The
        timeout bounds that: run_in_executor cannot be cancelled, so the
        worker thread may stay stuck, but we stop waiting on it and drop the
        transport so the read loop reconnects.
        """
        gap = TX_GAP_SECONDS - (time.monotonic() - self._last_tx)
        if gap > 0:
            await asyncio.sleep(gap)

        loop = asyncio.get_event_loop()
        if self._serial:
            write = loop.run_in_executor(None, self._serial.write, packet)
        elif self._socket:
            # sendall() loops internally until all bytes are written or an
            # error is raised, safer than send() for the multi-byte packets
            # we emit here.
            write = loop.run_in_executor(None, self._socket.sendall, packet)
        else:
            raise ConnectionError("No transport available")

        try:
            await asyncio.wait_for(write, timeout=TX_WRITE_TIMEOUT)
        except asyncio.TimeoutError:
            self._connected = False
            # Drop the transport, otherwise the read loop keeps reading from a
            # port we can no longer write to and nothing triggers a reconnect.
            asyncio.create_task(self._close_transport())
            raise TransportLostError(
                f"Write stalled for {TX_WRITE_TIMEOUT * 1000:.0f} ms, transport dropped"
            )
        finally:
            self._last_tx = time.monotonic()

    async def _send_radio_packet(self, packet: bytes, label: str, telegram: str = "") -> bool:
        """Write one radio telegram and check what the transceiver made of it.

        Call while holding _tx_slot(). The module answers every radio packet
        with a RESPONSE carrying a return code, and a full transmit queue is
        reported as RET_NOT_OK. Ignoring that response is what used to make
        dropped commands invisible: the state echo went out regardless and
        Home Assistant showed a device as switched that never heard anything.

        telegram is the debug line for the packet that just went out. Every
        telegram gets one, including both halves of a press/release pair:
        beta7 logged it only for single telegrams, which left the RPS paths
        (switches and covers) silent and made a field log readable only by
        counting response packets.
        """
        loop = asyncio.get_event_loop()
        self._response_future = loop.create_future()
        try:
            await self._write_packet(packet)
            if telegram:
                logger.debug(telegram)
            ret = await asyncio.wait_for(self._response_future, timeout=TX_RESPONSE_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(
                f"No transceiver ack for {label} within {TX_RESPONSE_TIMEOUT * 1000:.0f} ms"
            )
            return False
        except TransportLostError as e:
            logger.error(f"Transport error sending {label}: {e}")
            return False
        except (ConnectionError, serial.SerialException, OSError) as e:
            logger.error(f"Transport error sending {label}: {e}")
            self._connected = False
            return False
        finally:
            self._response_future = None

        if ret and ret[0] != RET_OK:
            logger.warning(f"Transceiver rejected {label}: return code 0x{ret[0]:02X}")
            return False
        return True

    async def _send_command(self, command_code: int) -> bytes:
        """Send an ESP3 common command and wait for response.

        Takes the same transmit slot as radio telegrams. Response packets
        carry no sequence number, so with two requests in flight the read
        loop would hand a radio acknowledgement to whoever asked for a
        version string.

        Raises:
            NotConnectedError: transport is not open
            CommandTimeoutError: no response in time
            TransportLostError: transport died during the exchange
            TransceiverBusyError: transmit slot was occupied
        """
        if not self._connected:
            raise NotConnectedError(f"Cannot send 0x{command_code:02X}: transceiver not connected")

        packet_data = bytes([command_code])
        header = bytes([0x00, len(packet_data), 0x00, PACKET_TYPE_COMMON_COMMAND])
        header_crc = crc8(header)
        data_crc = crc8(packet_data)
        packet = bytes([SYNC_BYTE]) + header + bytes([header_crc]) + packet_data + bytes([data_crc])

        async with self._tx_slot():
            loop = asyncio.get_event_loop()
            self._response_future = loop.create_future()

            try:
                await self._write_packet(packet)
                return await asyncio.wait_for(
                    self._response_future, timeout=COMMAND_RESPONSE_TIMEOUT
                )
            except asyncio.TimeoutError:
                raise CommandTimeoutError(
                    f"No response to command 0x{command_code:02X} after "
                    f"{COMMAND_RESPONSE_TIMEOUT:.0f}s"
                )
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
        # DB0=0x28: bit3=1 (data, not teach-in), bit5=1, "wakes up" the actuator
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

    # --- Eltako shutter command path, EEP A5-3F-7F ------------------------
    # Eltako, "Inhalte der Eltako-Funktelegramme", sections FJ62/12-36V DC,
    # FJ62NP-230V:
    #   teach-in  00 00 00 28 unlocks the learn mode, FF F8 0D 80 teaches the
    #             gateway in as GFVS (A5-3F-7F, manufacturer 0x00D). The
    #             actuator then switches its confirmation telegrams on by
    #             itself and locks the learn mode again.
    #   command   DB3+DB2 runtime, DB1 0x00 stop / 0x01 up / 0x02 down,
    #             DB0 bit3 data telegram, bit2 block for pushbuttons (kept at
    #             0), bit1 time base (0 = seconds in DB2, 1 = 100 ms over
    #             DB3+DB2). The actuator's own runtime is ignored whenever a
    #             time is sent, so every command carries one.
    # Cross-checked against openHAB's A5_3F_7F_EltakoFSB, which encodes a
    # percentage move the same way. See ADR-0015 and issue #40.
    ELTAKO_GFVS_UNLOCK = bytes([0x00, 0x00, 0x00, 0x28])
    ELTAKO_GFVS_TEACH_IN = bytes([0xFF, 0xF8, 0x0D, 0x80])

    _ELTAKO_COVER_DIR = {"STOP": 0x00, "OPEN": 0x01, "CLOSE": 0x02}
    _ELTAKO_COVER_100MS = 0x0A    # data telegram, runtime in 100 ms
    _ELTAKO_COVER_SECONDS = 0x08  # data telegram, runtime in seconds

    async def send_a5_3f_teach_in(self, destination: int, sender_offset: int = 1,
                                  repeats: int = 4) -> bool:
        """Teach the gateway into an Eltako shutter actuator as GFVS.

        This is a different teach-in from the directional pushbutton one: it is
        what makes the actuator accept the A5-3F-7F travel commands that drive
        it to a position.

        Eltako names no repeat count for GFVS, and a single telegram is easy to
        miss: the reporter of #40 needed four rounds of the pushbutton teach-in
        before an FJ62 took it. The sequence is repeated for that reason, which
        costs nothing once the actuator has learned it and locked its learn
        mode.

        Returns True when every telegram was acknowledged by the transceiver.
        """
        sender_id = self.get_sender_id(sender_offset)
        if sender_id is None:
            logger.error("Cannot send teach-in: base ID not read yet")
            return False

        # Broadcast, like every other teach-in here: an Eltako actuator in
        # learn mode stores the sender ID out of the telegram, it does not
        # match on the destination.
        broadcast = 0xFFFFFFFF
        rounds = max(1, min(int(repeats or 1), 10))
        logger.info(
            f"=== GFVS TEACH-IN (A5-3F-7F) === sender=0x{sender_id:08X}, "
            f"dest=0x{destination:08X}, {rounds} rounds"
        )

        ok = True
        for i in range(rounds):
            logger.info(f"  [{i + 1}/{rounds}] unlock 00000028, then teach-in FFF80D80")
            ok &= await self.send_telegram(
                sender_id=sender_id, rorg=0xA5,
                data=self.ELTAKO_GFVS_UNLOCK, destination=broadcast
            )
            await asyncio.sleep(1.0)
            ok &= await self.send_telegram(
                sender_id=sender_id, rorg=0xA5,
                data=self.ELTAKO_GFVS_TEACH_IN, destination=broadcast
            )
            if i < rounds - 1:
                await asyncio.sleep(1.0)

        logger.info(f"=== GFVS TEACH-IN COMPLETE === {rounds * 2} telegrams")
        return bool(ok)

    async def send_a5_eltako_cover_command(self, sender_id: int, command: str,
                                           seconds: float = 0.0,
                                           invert: bool = False,
                                           label: str = "") -> bool:
        """Send one A5-3F-7F travel command to an Eltako shutter actuator.

        command is OPEN, CLOSE or STOP, seconds the runtime of a travel. The
        runtime goes out in 100 ms steps: in whole seconds, a 30 s shutter
        could only be driven in steps of 3 %.

        invert swaps up and down for a reverse-mounted shutter, the same flag
        and the same meaning as on the rocker path.
        """
        direction = self._ELTAKO_COVER_DIR.get(command)
        if direction is None:
            logger.warning(f"Unknown Eltako cover command '{command}'")
            return False

        name = label or f"{sender_id:08X}"

        if command == "STOP":
            # A stop carries no runtime. DB2 = 0xFF on the seconds base is what
            # openHAB sends, and the actuator stops on DB1 = 0x00 regardless.
            data = bytes([0x00, 0xFF, 0x00, self._ELTAKO_COVER_SECONDS])
            logger.info(f"Sending A5-3F-7F STOP to {name}")
        else:
            if invert:
                direction = 0x02 if direction == 0x01 else 0x01
            tenths = int(round(max(0.0, seconds) * 10))
            if tenths <= 0:
                logger.warning(f"A5-3F-7F {command} for {name}: no runtime, not sent")
                return False
            tenths = min(tenths, 0xFFFF)
            data = bytes([(tenths >> 8) & 0xFF, tenths & 0xFF, direction,
                          self._ELTAKO_COVER_100MS])
            inv = " (inverted)" if invert else ""
            logger.info(
                f"Sending A5-3F-7F {command} for {tenths / 10:.1f}s to {name}{inv}"
            )

        return await self.send_telegram(
            sender_id=sender_id, rorg=0xA5, data=data, destination=0xFFFFFFFF
        )

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

    async def send_d2_05_command(self, sender_id: int, destination: int,
                                 command: str, ha_position: int = None,
                                 channel: int = 0, invert: bool = False) -> bool:
        """Send a D2-05-00 (Blinds Control for Position and Angle) VLD command.

        Unlike Eltako actuators, which react to simulated F6 rocker presses,
        NodOn/EnOcean D2-05-00 shutter modules expect a structured VLD telegram
        (RORG 0xD2) that carries the command in the payload. This is an
        *addressed* telegram: destination is the actuator's own ID.

        D2-05-00 message layouts differ per command:
          "Go to Position and Angle" (CMD 1), 4 data bytes:
            DB3 = POS  Position 0..100 %, 127 (0x7F) = "do not change / not used"
            DB2 = ANG  Angle    0..100 %, 127 (0x7F) = not used
            DB1 = REPO(bits 7..4) | LOCK(bits 3..0) , 0 = normal repositioning
            DB0 = CHN (bits 7..4) | CMD (bits 3..0) = 1
          "Stop" (CMD 2), 1 data byte:
            DB0 = CHN (bits 7..4) | CMD (bits 3..0) = 2
        The Stop command carries no POS/ANG/REPO fields, so it MUST be a
        single byte, sending the 4-byte layout makes the actuator reject it
        (the reason Stop did nothing in issue #2).

        Position convention differs between EnOcean and Home Assistant:
            EnOcean D2-05: 0 % = fully open (up), 100 % = fully closed (down)
            Home Assistant: 100 = open, 0 = closed
        so HA positions are inverted here (enocean_pos = 100 - ha_pos), and
        OPEN maps to EnOcean 0 %, CLOSE to 100 %.

        Args:
            sender_id: Controller ID the actuator was taught in with (int)
            destination: Actuator address (int), addressed, not broadcast
            command: "OPEN", "CLOSE", "STOP" or "POSITION"
            ha_position: Target position 0..100 in HA convention (POSITION only)
            channel: Output channel (default 0)
            invert: Reverse direction for shutters wired/mounted the other way:
                OPEN/CLOSE are swapped and the HA->EnOcean position mapping is
                not inverted. Must match the position-feedback inversion in the
                MQTT discovery config (see mapping_manager).
        """
        cmd = command.strip().upper()
        chn_nibble = (channel & 0x0F) << 4

        if cmd == "STOP":
            # Stop is a single-byte message: CHN | CMD 2. No POS/ANG/REPO.
            data = bytes([chn_nibble | 0x02])
        else:
            # Normal wiring: EnOcean 0 % = fully open, 100 % = fully closed,
            # HA 100 = open. `invert` flips this for reverse-wired shutters.
            if cmd == "OPEN":
                enocean_pos = 100 if invert else 0
            elif cmd == "CLOSE":
                enocean_pos = 0 if invert else 100
            elif cmd == "POSITION":
                if ha_position is None:
                    logger.warning("D2-05 POSITION command without ha_position")
                    return False
                ha_pos = max(0, min(100, int(ha_position)))
                enocean_pos = ha_pos if invert else (100 - ha_pos)
            else:
                logger.warning(f"Unknown D2-05 command: {command}")
                return False
            # Go to Position (CMD 1); angle "not used" so the slat angle is
            # left to the actuator's own logic.
            data = bytes([enocean_pos & 0xFF, 0x7F, 0x00, chn_nibble | 0x01])

        logger.info(
            f"Sending D2-05-00 {cmd} (data={data.hex().upper()}) "
            f"sender=0x{sender_id:08X} dest=0x{destination:08X}"
        )

        return await self.send_telegram(
            sender_id=sender_id,
            rorg=0xD2,
            data=data,
            destination=destination,
            status=0x00
        )

    async def send_d2_01_command(self, sender_id: int, destination: int,
                                 command: str, channel: int = 0) -> bool:
        """Send a D2-01 (Electronic switch/dimmer) "Actuator Set Output" command.

        D2-01-xx actuators (e.g. NodOn In-Wall relay / boiler contact,
        EEP D2-01-0F) are VLD (RORG 0xD2) devices, they do NOT react to F6
        rocker presses. Driving them with an F6 broadcast both fails to switch
        them AND makes other broadcast-listening actuators (e.g. a D2-05 blind)
        move by mistake (issue #2). This sends the proper addressed telegram.

        "Actuator Set Output" (CMD 1), 3 data bytes:
            DB2 = ...CMD(bits 3..0) = 1
            DB1 = DV(bits 7..5) | IO(bits 4..0)   DV 0 = switch to new value
            DB0 = OV(bits 6..0)                    0 = OFF, 1..100 = ON at %
        Verified against the EnOcean EEP D2-01 profile (python-enocean).

        Args:
            sender_id: Controller ID the actuator was taught in with (int)
            destination: Actuator address (int), addressed, not broadcast
            command: "ON" / "OFF", or a numeric string / int 0-100 (dim level)
            channel: I/O channel (0 = first output, 1 = second output on
                2-channel modules like the NodOn SIN-2-2-01)
        """
        cmd = str(command).strip().upper()
        io = channel & 0x1F                 # IO channel, DV = 0 (switch)
        if cmd == "ON":
            ov = 100                        # fully on
        elif cmd == "OFF":
            ov = 0
        else:
            # Dim level from HA (0-100). A "light" role on a D2-01 dimmer sends
            # the brightness directly; 0 means off.
            try:
                ov = max(0, min(100, int(float(cmd))))
            except (TypeError, ValueError):
                logger.warning(f"Unknown D2-01 command: {command}")
                return False

        data = bytes([0x01, io, ov & 0x7F])
        logger.info(
            f"Sending D2-01 {cmd} (ch={channel} out={ov}% data={data.hex().upper()}) "
            f"sender=0x{sender_id:08X} dest=0x{destination:08X}"
        )
        return await self.send_telegram(
            sender_id=sender_id,
            rorg=0xD2,
            data=data,
            destination=destination,
            status=0x00
        )

    def register_telegram_callback(self, callback: Callable):
        """Register callback for received telegrams"""
        self._telegram_callbacks.append(callback)

    def set_teach_in_callback(self, callback: Callable):
        """Set callback for teach-in events"""
        self._teach_in_callback = callback

    def _build_radio_packet(self, sender_id: int, rorg: int, data: bytes,
                            destination: int = 0xFFFFFFFF, status: int = None) -> bytes:
        """Assemble an ESP3 RADIO_ERP1 packet."""
        # RORG + data + sender_id (4 bytes) + status (1 byte)
        sender_bytes = sender_id.to_bytes(4, 'big')
        if status is None:
            # F6 (RPS) needs T21 flag (0x30 for pressed, 0x20 for released)
            status = 0x30 if (rorg == 0xF6 and data and data[0] != 0x00) else 0x00

        packet_data = bytes([rorg]) + data + sender_bytes + bytes([status])

        # Optional data: SubTelNum, DestinationID, dBm, SecurityLevel
        dest_bytes = destination.to_bytes(4, 'big')
        optional = bytes([0x03]) + dest_bytes + bytes([0xFF, 0x00])

        header = bytes([
            (len(packet_data) >> 8) & 0xFF,
            len(packet_data) & 0xFF,
            len(optional),
            PACKET_TYPE_RADIO
        ])

        header_crc = crc8(header)
        data_crc = crc8(packet_data + optional)

        return (bytes([SYNC_BYTE]) + header + bytes([header_crc])
                + packet_data + optional + bytes([data_crc]))

    async def send_telegram(self, sender_id: int, rorg: int, data: bytes, destination: int = 0xFFFFFFFF, status: int = None):
        """Send an EnOcean telegram.

        Returns True only when the transceiver acknowledged it, so callers can
        skip the optimistic state echo for a command that never went out.
        """
        if not self._connected:
            logger.error("Cannot send - not connected")
            return False

        packet = self._build_radio_packet(sender_id, rorg, data, destination, status)
        label = f"RORG={rorg:02X} Data={data.hex()} Dest={destination:08X}"
        telegram = _radio_log_line(rorg, data, destination)

        try:
            async with self._tx_slot():
                return await self._send_radio_packet(packet, label, telegram)
        except TransceiverBusyError as e:
            logger.error(f"Cannot send {label}: {e}")
            return False

    async def send_rps_press_release(self, sender_id: int, press_data: int,
                                     destination: int = 0xFFFFFFFF,
                                     hold: float = RPS_HOLD_SECONDS,
                                     label: str = "") -> bool:
        """Simulate one short rocker press: press, hold, release.

        The pair is sent inside a single transmit slot, so no other telegram
        can slip between press and release and stretch the hold. That matters
        because the hold *is* the command for Eltako actuators, see
        RPS_HOLD_SECONDS.

        The release is sent from a finally block and the whole pair is
        shielded by the public wrapper: an abandoned press leaves a shutter
        running until its own travel time expires, so it must go out even when
        the caller is cancelled or the press was not acknowledged.
        """
        if not self._connected:
            logger.error("Cannot send - not connected")
            return False

        return await asyncio.shield(
            self._send_rps_pair(sender_id, press_data, destination, hold, label)
        )

    async def _send_rps_pair(self, sender_id: int, press_data: int, destination: int,
                             hold: float, label: str) -> bool:
        press = self._build_radio_packet(sender_id, 0xF6, bytes([press_data]),
                                         destination, 0x30)
        release = self._build_radio_packet(sender_id, 0xF6, bytes([0x00]),
                                          destination, 0x20)
        press_line = _radio_log_line(0xF6, bytes([press_data]), destination)
        release_line = _radio_log_line(0xF6, bytes([0x00]), destination)
        name = label or f"{sender_id:08X}"

        try:
            async with self._tx_slot():
                press_ok = await self._send_radio_packet(press, f"{name} press", press_line)
                # _last_tx is the moment the packet went out. Measure the hold
                # write to write: that is what the actuator sees. Timing it
                # around the calls instead would count the module's
                # acknowledgement latency, which happens after the telegram is
                # already on the air.
                pressed_at = self._last_tx
                try:
                    await asyncio.sleep(hold)
                finally:
                    release_ok = await self._send_radio_packet(
                        release, f"{name} release", release_line
                    )
                    held = self._last_tx - pressed_at
                    if held > RPS_HOLD_WARN_SECONDS:
                        logger.warning(
                            f"RPS press for {name} held {held * 1000:.0f} ms, "
                            f"actuators may read this as a long press"
                        )
        except TransceiverBusyError as e:
            logger.error(f"Cannot send RPS pair for {name}: {e}")
            return False

        return press_ok and release_ok
