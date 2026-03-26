"""
EnOcean MQTT - All-in-One Home Assistant Add-on
Main application entry point

Compatible with ChristopheHD/HA_enoceanmqtt-addon MQTT patterns.
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# Import API routers
from api import devices, eep, mappings, system, gateway

# Import core components
from core.mqtt_handler import MQTTHandler
from core.serial_handler import SerialHandler
from core.device_manager import DeviceManager
from core.eep_manager import EEPManager
from core.mapping_manager import MappingManager
from core.telegram_buffer import TelegramBuffer

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()
_log_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Apply log level to root and all third-party loggers
logging.getLogger().setLevel(_log_level)
for _name in ("uvicorn", "uvicorn.access", "uvicorn.error", "paho.mqtt", "paho.mqtt.client"):
    logging.getLogger(_name).setLevel(_log_level)
logger = logging.getLogger(__name__)

# Configuration
# /data/ is the correct persistent storage for HA addons (survives updates)
CONFIG_PATH = os.getenv("CONFIG_PATH", "/data")
ENOCEAN_PORT = os.getenv("ENOCEAN_PORT", "")
CACHE_DEVICE_STATES = os.getenv("CACHE_DEVICE_STATES", "true").lower() == "true"
VERSION = "1.2.1"

# Global instances
mqtt_handler: MQTTHandler = None
serial_handler: SerialHandler = None
device_manager: DeviceManager = None
eep_manager: EEPManager = None
mapping_manager: MappingManager = None
telegram_buffer: TelegramBuffer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    global mqtt_handler, serial_handler, device_manager, eep_manager, mapping_manager, telegram_buffer

    logger.info("Starting EnOcean MQTT Add-on...")

    # Initialize Telegram Buffer
    telegram_buffer = TelegramBuffer(max_size=200)

    # Initialize EEP Manager
    eep_manager = EEPManager(CONFIG_PATH)
    await eep_manager.initialize()
    logger.info(f"Loaded {eep_manager.profile_count} EEP profiles")

    # Initialize Mapping Manager (with eep_manager for ha_mapping lookup)
    mapping_manager = MappingManager(CONFIG_PATH, eep_manager=eep_manager)
    await mapping_manager.initialize()

    # Initialize Device Manager
    device_manager = DeviceManager(CONFIG_PATH, eep_manager)
    await device_manager.load_devices()
    logger.info(f"Loaded {device_manager.device_count} devices")

    # Initialize MQTT Handler
    mqtt_host = os.getenv("MQTT_HOST", "")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_user = os.getenv("MQTT_USER", "")
    mqtt_password = os.getenv("MQTT_PASSWORD", "")
    mqtt_prefix = os.getenv("MQTT_PREFIX", "enoceanmqtt")
    mqtt_discovery_prefix = os.getenv("MQTT_DISCOVERY_PREFIX", "homeassistant")

    if mqtt_host:
        mqtt_handler = MQTTHandler(
            host=mqtt_host,
            port=mqtt_port,
            username=mqtt_user,
            password=mqtt_password,
            prefix=mqtt_prefix,
            discovery_prefix=mqtt_discovery_prefix,
            device_manager=device_manager,
            config_path=CONFIG_PATH,
            cache_states=CACHE_DEVICE_STATES
        )
        await mqtt_handler.connect()
        logger.info(f"Connected to MQTT broker at {mqtt_host}:{mqtt_port}")

        # Load persisted states into memory (published AFTER discoveries below)
        if CACHE_DEVICE_STATES:
            await mqtt_handler.load_persisted_states()
            logger.info("Device state caching enabled")
    else:
        logger.warning("MQTT not configured - running in UI-only mode")

    # Initialize Serial Handler (EnOcean communication)
    if ENOCEAN_PORT:
        serial_handler = SerialHandler(
            port=ENOCEAN_PORT,
            device_manager=device_manager,
            mqtt_handler=mqtt_handler,
            eep_manager=eep_manager,
            telegram_buffer=telegram_buffer
        )
        await serial_handler.connect()
        logger.info(f"Connected to EnOcean transceiver at {ENOCEAN_PORT}")
    else:
        logger.warning("EnOcean port not configured - running without EnOcean communication")

    # Publish HA discovery for all devices
    if mqtt_handler and device_manager and mapping_manager:
        await _publish_all_discoveries()

        # Set birth message callback - re-publishes discoveries when HA restarts
        # or when MQTT broker reconnects
        mqtt_handler.set_ha_birth_callback(_publish_all_discoveries)

        # Set command callback - routes MQTT commands to EnOcean telegrams
        mqtt_handler.set_device_command_callback(_handle_device_command)

    # Store instances in app state for access in routes
    app.state.mqtt_handler = mqtt_handler
    app.state.serial_handler = serial_handler
    app.state.device_manager = device_manager
    app.state.eep_manager = eep_manager
    app.state.mapping_manager = mapping_manager
    app.state.telegram_buffer = telegram_buffer
    app.state.config_path = CONFIG_PATH

    logger.info("EnOcean MQTT Add-on started successfully — Web UI running on port 8099")

    yield

    # Shutdown
    logger.info("Shutting down EnOcean MQTT Add-on...")

    if serial_handler:
        await serial_handler.disconnect()

    if mqtt_handler:
        # disconnect() publishes offline status for all devices and gateway
        await mqtt_handler.disconnect()

    logger.info("EnOcean MQTT Add-on stopped")


async def _publish_all_discoveries():
    """Publish HA MQTT discovery and availability for all configured devices,
    then re-publish cached states.

    Called on startup, on HA birth message (HA restart), and on MQTT reconnect.

    IMPORTANT: States are published AFTER discoveries so that HA evaluates
    state values with the correct entity configuration (e.g., binary_sensor
    payload_on/payload_off). Publishing states before discoveries causes
    binary_sensors to show 'Unknown' because HA evaluates them with default
    payload_on="ON"/payload_off="OFF" before the custom config arrives.
    """
    global mqtt_handler, device_manager, mapping_manager

    if not mqtt_handler or not device_manager or not mapping_manager:
        return

    logger.info("Publishing HA discovery for all devices...")

    for device in device_manager.devices.values():
        try:
            # Build device info for HA
            device_info = mapping_manager.build_device_info(device)

            # Generate discovery configs
            configs = mapping_manager.get_ha_discovery_configs(
                device_name=device.name,
                eep_id=device.eep_id,
                device_address=device.address,
                device_sender=device.sender_id,
                mqtt_prefix=mqtt_handler.prefix,
                device_info=device_info,
                actuator_type=device.actuator_type
            )

            # Publish each entity discovery config
            for item in configs:
                await mqtt_handler.publish_discovery_config(
                    component=item["component"],
                    unique_id=item["unique_id"],
                    config=item["config"]
                )

            # Publish device availability (online)
            await mqtt_handler.publish_device_availability(device.name, available=True)

            logger.debug(f"Published discovery for {device.name}")

        except Exception as e:
            logger.error(f"Failed to publish discovery for {device.name}: {e}")

    logger.info(f"Published HA discovery for {device_manager.device_count} devices")

    # Re-publish cached states AFTER all discoveries are sent
    # Give HA time to process discovery configs before sending states
    if mqtt_handler.cache_states:
        await asyncio.sleep(2)
        await mqtt_handler.republish_cached_states()


async def _handle_device_command(device_name: str, payload: str, entity: str = None):
    """Handle MQTT command for an actuator device — send F6 telegram.

    For Eltako actuators (FD62NPN, FSR61, FSB61, etc.):
    - ON: F6 rocker B top (BI) press + release
    - OFF: F6 rocker B bottom (B0) press + release
    """
    global serial_handler, device_manager

    if not serial_handler or not serial_handler.is_connected:
        logger.warning(f"Cannot send command for {device_name}: serial not connected")
        return

    if not device_manager:
        return

    device = device_manager.get_device(device_name)
    if not device:
        logger.warning(f"Command for unknown device: {device_name}")
        return

    if not device.actuator_type:
        logger.debug(f"Ignoring command for sensor-only device: {device_name}")
        return

    if not device.sender_id:
        logger.warning(f"Cannot send command for {device_name}: no sender_id configured")
        return

    # Parse sender ID to integer
    try:
        sender_id = int(device.sender_id.replace("0x", "").replace("0X", ""), 16)
        destination = int(device.address.replace("0x", "").replace("0X", ""), 16)
    except ValueError as e:
        logger.error(f"Invalid address for {device_name}: {e}")
        return

    command = payload.strip().upper()
    logger.info(f"Actuator command: {device_name} ({device.actuator_type}) = {command}")

    # F6 rocker commands use BROADCAST like real EnOcean pushbuttons.
    # Eltako actuators match by sender ID, not by destination address.
    broadcast = 0xFFFFFFFF

    if device.actuator_type == "light":
        # Dimmers use A5-38-08 Central Command Dimming
        # With on_command_type=brightness, HA sends brightness (0-100) for ON,
        # "OFF" for off. "ON" text only from manual MQTT publish.
        if command == "ON":
            # Turn on at stored brightness (dim_mode=0)
            await serial_handler.send_a5_dimmer_command(sender_id, "ON")
            logger.info(f"Sent ON (A5-38-08 stored brightness) to {device_name}")
        elif command == "OFF":
            await serial_handler.send_a5_dimmer_command(sender_id, "OFF")
            logger.info(f"Sent OFF (A5-38-08) to {device_name}")
        else:
            # Brightness value from HA (0-100) — send as 0-100 directly
            # Eltako dimmers use 0-100 range (not standard 0-255)
            try:
                val = int(command)
                dim = max(0, min(100, val))
                if dim == 0:
                    await serial_handler.send_a5_dimmer_command(sender_id, "OFF")
                    logger.info(f"Sent OFF (A5-38-08 brightness=0) to {device_name}")
                else:
                    # DIM mode: dim_mode=1 (use DB2 value) — actually sets brightness
                    await serial_handler.send_a5_dimmer_command(sender_id, "DIM", dim_value=dim)
                    logger.info(f"Sent DIM (A5-38-08 dim={dim}, {val}%) to {device_name}")
            except ValueError:
                logger.warning(f"Unknown command '{command}' for dimmer {device_name}")

    elif device.actuator_type == "switch":
        if command == "ON":
            # F6 Rocker B top (BI) pressed: data=0x50, status=0x30 (T21+NU)
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x50]), destination=broadcast, status=0x30
            )
            await asyncio.sleep(0.1)
            # Release: data=0x00, status=0x20 (T21, no NU)
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x00]), destination=broadcast, status=0x20
            )
            logger.info(f"Sent ON (F6 BI press+release) to {device_name}")

        elif command == "OFF":
            # F6 Rocker B bottom (B0) pressed: data=0x70, status=0x30 (T21+NU)
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x70]), destination=broadcast, status=0x30
            )
            await asyncio.sleep(0.1)
            # Release: data=0x00, status=0x20 (T21, no NU)
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x00]), destination=broadcast, status=0x20
            )
            logger.info(f"Sent OFF (F6 B0 press+release) to {device_name}")

        else:
            logger.warning(f"Unknown command '{command}' for {device_name}")

    elif device.actuator_type == "cover":
        if command == "OPEN":
            # BI press+release for open/up
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x50]), destination=broadcast, status=0x30
            )
            await asyncio.sleep(0.1)
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x00]), destination=broadcast, status=0x20
            )
        elif command == "CLOSE":
            # B0 press+release for close/down
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x70]), destination=broadcast, status=0x30
            )
            await asyncio.sleep(0.1)
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x00]), destination=broadcast, status=0x20
            )
        elif command == "STOP":
            # Any release without prior press = stop
            await serial_handler.send_telegram(
                sender_id=sender_id, rorg=0xF6,
                data=bytes([0x00]), destination=broadcast, status=0x20
            )


# Create FastAPI app
app = FastAPI(
    title="EnOcean MQTT UI",
    description="All-in-One EnOcean to MQTT bridge with web UI",
    version=VERSION,
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(eep.router, prefix="/api/eep", tags=["eep"])
app.include_router(mappings.router, prefix="/api/mappings", tags=["mappings"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(gateway.router, prefix="/api/gateway", tags=["gateway"])


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main UI"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": VERSION
    })


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "mqtt_connected": mqtt_handler.is_connected if mqtt_handler else False,
        "enocean_connected": serial_handler.is_connected if serial_handler else False,
        "device_count": device_manager.device_count if device_manager else 0,
        "profile_count": eep_manager.profile_count if eep_manager else 0
    }


if __name__ == "__main__":
    import uvicorn
    # Suppress uvicorn's own startup messages ("Uvicorn running on http://0.0.0.0:8099",
    # "Application startup complete") which confuse users.
    # Our own "started successfully" message in the lifespan is clearer.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8099,
        log_level="warning",
        log_config=None
    )
