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
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
# /data/ is the correct persistent storage for HA addons (survives updates)
CONFIG_PATH = os.getenv("CONFIG_PATH", "/data")
ENOCEAN_PORT = os.getenv("ENOCEAN_PORT", "")
CACHE_DEVICE_STATES = os.getenv("CACHE_DEVICE_STATES", "true").lower() == "true"
VERSION = "2.1.11"

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

    # Store instances in app state for access in routes
    app.state.mqtt_handler = mqtt_handler
    app.state.serial_handler = serial_handler
    app.state.device_manager = device_manager
    app.state.eep_manager = eep_manager
    app.state.mapping_manager = mapping_manager
    app.state.telegram_buffer = telegram_buffer
    app.state.config_path = CONFIG_PATH

    logger.info("EnOcean MQTT Add-on started successfully")

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
                device_info=device_info
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


# Create FastAPI app
app = FastAPI(
    title="EnOcean MQTT",
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
    uvicorn.run(app, host="0.0.0.0", port=8099)
