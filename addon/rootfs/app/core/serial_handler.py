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
        """Connect via TCP"""
        parts = self.port.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid TCP port format: {self.port}")

        host = parts[1]
        port = int(parts[2])

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5.0)
        self._socket.connect((host, port))
        self._socket.settimeout(1.0)

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

        if self._serial:
            self._serial.close()
            self._serial = None

        if self._socket:
            self._socket.close()
            self._socket = None

        self._connected = False
        logger.info("Disconnected from EnOcean transceiver")

    async def _read_loop(self):
        """Main read loop using run_in_executor for blocking serial reads.

        This approach is proven to work with EnOcean USB sticks.
        """
        loop = asyncio.get_event_loop()
        timeout_count = 0
        packet_count = 0

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
                logger.info(f"ESP3 packet #{packet_count}: type={packet_type:#04x} data_len={data_len} opt_len={optional_len}")

                # Process by packet type
                if packet_type == PACKET_TYPE_RADIO:
                    await self._process_radio_telegram(packet_data, optional_data)
                elif packet_type == PACKET_TYPE_RESPONSE:
                    logger.debug(f"Response packet: {packet_data.hex()}")
                elif packet_type == PACKET_TYPE_EVENT:
                    logger.info(f"Event packet: {packet_data.hex()}")

            except asyncio.CancelledError:
                break
            except serial.SerialException as e:
                logger.error(f"Serial error: {e}")
                self._connected = False
                break
            except Exception as e:
                if self._running:
                    logger.error(f"Error in read loop: {e}", exc_info=True)
                    await asyncio.sleep(1)

        logger.info("Serial read loop stopped")

    def _serial_read(self, size: int) -> bytes:
        """Blocking serial read - called via run_in_executor"""
        try:
            if self._serial and self._serial.is_open:
                return self._serial.read(size)
        except Exception as e:
            if self._running:
                logger.error(f"Serial read error: {e}")
        return b""

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
        dbm = 0
        if len(optional) >= 5:
            dbm = -optional[4]

        telegram = RadioTelegram(
            rorg=rorg,
            data=payload,
            sender_id=sender_id,
            status=status,
            dbm=dbm
        )

        logger.info(f"RX [{telegram.sender_hex}] RORG={telegram.rorg_hex} Data={telegram.data.hex().upper()} dBm={telegram.dbm}")

        # Check if this is a teach-in telegram
        is_teach_in = self._is_teach_in(telegram)
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

        # Decode telegram using EEP profile
        decoded = self._decode_telegram(telegram, profile)

        logger.info(f"RX [{telegram.sender_hex}] Device={device.name} EEP={device.eep_id} Decoded={decoded}")

        # Publish to MQTT
        if self.mqtt_handler:
            await self.mqtt_handler.publish_state(device.name, decoded)
            logger.info(f"TX MQTT [{device.name}] Published state to {self.mqtt_handler.prefix}/{device.name}/state")

        return device.name, device.eep_id, decoded

    def _decode_telegram(self, telegram: RadioTelegram, profile) -> Dict[str, Any]:
        """Decode telegram data using EEP profile"""
        decoded = {
            "sender_id": telegram.sender_hex,
            "rssi": telegram.dbm
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

        return decoded

    def register_telegram_callback(self, callback: Callable):
        """Register callback for received telegrams"""
        self._telegram_callbacks.append(callback)

    def set_teach_in_callback(self, callback: Callable):
        """Set callback for teach-in events"""
        self._teach_in_callback = callback

    async def send_telegram(self, sender_id: int, rorg: int, data: bytes, destination: int = 0xFFFFFFFF):
        """Send an EnOcean telegram"""
        if not self._connected:
            logger.error("Cannot send - not connected")
            return False

        # Build radio telegram
        # RORG + data + sender_id (4 bytes) + status (1 byte)
        sender_bytes = sender_id.to_bytes(4, 'big')
        status = 0x00

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

        # Send packet
        try:
            if self._serial:
                self._serial.write(packet)
            elif self._socket:
                self._socket.send(packet)

            logger.info(f"TX EnOcean: RORG={rorg:02X}, Data={data.hex()}, Dest={destination:08X}")
            return True

        except Exception as e:
            logger.error(f"Failed to send telegram: {e}")
            return False
