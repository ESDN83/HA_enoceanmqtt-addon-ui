"""
EnOcean MQTT - All-in-One Home Assistant Add-on
Main application entry point

Compatible with ChristopheHD/HA_enoceanmqtt-addon MQTT patterns.
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

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
# How often the availability watchdog looks at the clock (#37). The shortest
# timeout a user can set is a minute, so checking once a minute is enough; the
# cost of being late is at most one interval of delay on a device coming back.
AVAILABILITY_CHECK_SECONDS = 60
from app_version import VERSION  # single source of truth (reads config.yaml)

# Global instances
mqtt_handler: MQTTHandler = None
serial_handler: SerialHandler = None
device_manager: DeviceManager = None
eep_manager: EEPManager = None
mapping_manager: MappingManager = None
telegram_buffer: TelegramBuffer = None
availability_task: asyncio.Task = None
# Last availability the watchdog published per device, so the retained topic is
# only rewritten on a change, plus the moment the add-on came up (#37).
_availability_known: Dict[str, bool] = {}
_availability_started_at: Optional[datetime] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    global mqtt_handler, serial_handler, device_manager, eep_manager, mapping_manager, telegram_buffer
    global availability_task

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
        # No success log here. The broker's connect callback already logs it,
        # and only when it really happened: connect() returns after a timeout
        # too, so a second line here claimed a connection that might not exist.
        # Two identical "Connected to MQTT broker" lines also read like two
        # connections, which sent one debugging session down the wrong path.
        await mqtt_handler.connect()

        # Load persisted states into memory (published AFTER discoveries below)
        if CACHE_DEVICE_STATES:
            await mqtt_handler.load_persisted_states()
            logger.info("Device state caching enabled")
    else:
        logger.warning("MQTT not configured - running in UI-only mode")

    # Initialize Serial Handler (EnOcean communication).
    # A failing initial connect (gateway offline at startup) must NOT crash
    # the whole addon — otherwise the supervisor restarts us in a loop and
    # the UI is never reachable for reconfiguration. On failure we start a
    # background task that retries until the gateway comes up.
    if ENOCEAN_PORT:
        serial_handler = SerialHandler(
            port=ENOCEAN_PORT,
            device_manager=device_manager,
            mqtt_handler=mqtt_handler,
            eep_manager=eep_manager,
            telegram_buffer=telegram_buffer
        )
        try:
            await serial_handler.connect()
            logger.info(f"Connected to EnOcean transceiver at {ENOCEAN_PORT}")
        except Exception as e:
            logger.error(f"Initial EnOcean connect failed: {e} — will retry in background")
            asyncio.create_task(_serial_background_connect(serial_handler, ENOCEAN_PORT))
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
    # Handles for the API routers. They must NOT do 'from main import ...':
    # run.sh starts this file as 'python3 main.py', so the live module is
    # __main__ and importing 'main' builds a second, empty copy whose
    # globals are all None. Such a call then fails silently.
    app.state.publish_all_discoveries = _publish_all_discoveries
    app.state.echo_light_state = _echo_light_state
    app.state.availability_after_edit = _availability_after_edit

    # Started here, after the initial discovery and availability publish, so its
    # first pass cannot contradict what was just announced (#37).
    if mqtt_handler and device_manager:
        availability_task = asyncio.create_task(
            _availability_watchdog(datetime.now(timezone.utc))
        )

    logger.info("EnOcean MQTT Add-on started successfully — Web UI running on port 8099")

    yield

    # Shutdown
    logger.info("Shutting down EnOcean MQTT Add-on...")

    if availability_task:
        availability_task.cancel()
        try:
            await availability_task
        except asyncio.CancelledError:
            pass

    if serial_handler:
        await serial_handler.disconnect()

    if mqtt_handler:
        # disconnect() publishes offline status for all devices and gateway
        await mqtt_handler.disconnect()

    logger.info("EnOcean MQTT Add-on stopped")


async def _availability_watchdog(started_at: datetime):
    """Report devices unavailable once they have been silent for too long (#37).

    Opt-in per device: `availability_timeout` is minutes, 0 means never, which
    is the default and the behaviour of every earlier version. An actuator only
    transmits when it is switched, so a blanket watchdog would declare healthy
    hardware dead.

    The deadline is measured from the LATER of the device's last telegram and
    the add-on's own start. That covers both directions of the problem:

    - Judging by `last_seen` alone means a device that really died stays dead
      across restarts, which is the whole point. Resetting the clock at every
      start would clear the very case this exists for, because the state cache
      republishes the last known value on each start and makes a flat battery
      look freshly reported.
    - Judging by `last_seen` alone would also punish devices for the add-on
      being down: after a two-day outage every timestamp is old through no
      fault of any device. Starting the clock at boot gives each device one
      full interval to check in before anything is claimed about it.

    Availability is published only when it changes, so the retained topic is
    not rewritten every minute.
    """
    global _availability_started_at
    _availability_started_at = started_at
    _availability_known.clear()
    _availability_known.update({d: True for d in device_manager.devices})

    while True:
        try:
            await asyncio.sleep(AVAILABILITY_CHECK_SECONDS)
            if not mqtt_handler or not device_manager:
                continue

            for name in list(device_manager.devices):
                await _evaluate_availability(name)

            for gone in set(_availability_known) - set(device_manager.devices):
                _availability_known.pop(gone, None)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Availability watchdog failed: {e}")


async def _availability_after_edit(name: str):
    """Re-decide a device's availability right after it was saved.

    Saving republishes discovery, and `_publish_discovery` writes
    `availability=online` unconditionally. The watchdog's memory has to be
    aligned to that first, otherwise its next pass compares its own stale
    verdict against the unchanged truth, finds no difference, and never
    corrects the `online` the edit just wrote (#37).
    """
    _availability_known[name] = True
    await _evaluate_availability(name)


async def _evaluate_availability(name: str):
    """Decide whether one device counts as alive and publish only on a change.

    Also called straight after a device is edited. That matters: saving a device
    republishes its discovery and with it `availability=online` unconditionally,
    which would otherwise contradict a verdict this watchdog had already
    published. Worse, the watchdog would then see no change against its own
    memory and stay quiet, leaving a long-dead device reading "online" forever
    after an unrelated edit. Re-deciding right after the edit closes that.
    """
    if not mqtt_handler or not device_manager or _availability_started_at is None:
        return
    device = device_manager.get_device(name)
    if not device:
        return

    timeout = int(getattr(device, "availability_timeout", 0) or 0)
    now = datetime.now(timezone.utc)

    if timeout <= 0:
        # Watchdog switched off for this device. If it had been marked
        # unavailable earlier, undo that once rather than leaving it stuck.
        if _availability_known.get(name) is False:
            await mqtt_handler.publish_device_availability(name, available=True)
            _availability_known[name] = True
            logger.info(f"{name} availability watch is off, reported available again")
        else:
            _availability_known[name] = True
        return

    state = mqtt_handler.get_last_state(name) or {}
    last_seen = _parse_last_seen(state.get("last_seen"))
    reference = max(last_seen, _availability_started_at) if last_seen else _availability_started_at
    alive = (now - reference) < timedelta(minutes=timeout)

    if _availability_known.get(name) != alive:
        await mqtt_handler.publish_device_availability(name, available=alive)
        _availability_known[name] = alive
        silent = int((now - reference).total_seconds() // 60)
        logger.info(
            f"{name} is {'available again' if alive else 'unavailable'} "
            f"(silent for {silent} min, limit {timeout} min)"
        )


def _parse_last_seen(value) -> Optional[datetime]:
    """Read the cached `last_seen` timestamp, or None if it is missing or bad.

    Written by the serial handler as a UTC isoformat string. Anything without a
    timezone is read as UTC, so a comparison never raises on naive input.
    """
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


async def _serial_background_connect(handler, port: str):
    """Keep retrying serial_handler.connect() until the gateway comes up.

    Used when the gateway is unreachable at startup. Once connected, the
    SerialHandler's own read loop takes over reconnect duties on later
    drops. Backoff 5s -> 60s.
    """
    backoff = 5.0
    while True:
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            return
        try:
            await handler.connect()
            logger.info(f"EnOcean transceiver connected at {port} (was offline at startup)")
            return
        except Exception as e:
            logger.warning(f"Retry connect to {port} failed: {e} — next attempt in {min(backoff * 2, 60.0):.0f}s")
            backoff = min(backoff * 2, 60.0)


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
            # Naming for multi-channel modules lives in mapping_manager so this
            # startup republish and the create/update path in api/devices.py
            # cannot disagree. They did in beta7: this path republished channel
            # entities under their device name and the module under one
            # channel's description, silently undoing the edit path's naming on
            # every restart (ADR-0007).
            configs = mapping_manager.build_discovery_for_device(
                device, mqtt_handler.prefix,
                device_manager.get_devices_by_address(device.address)
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
        # Drop cached states of devices that are gone before anything is sent.
        # Deletes and renames made before 1.7.2 left their entries behind, and
        # every start republished them as retained state under a name nothing
        # points at, which a later device reusing that name would inherit (#36).
        await mqtt_handler.prune_cached_states(device_manager.devices.keys())
        await asyncio.sleep(2)
        await mqtt_handler.republish_cached_states()


async def _echo_switch_state(device_name: str, command: str):
    """Echo a commanded switch state to the device's state topic.

    Switch entities are not published as optimistic, because that makes Home
    Assistant mark them assumed_state and render two buttons instead of a
    toggle (ADR-0008). The toggle therefore needs a state to react to, and
    actuators without status reporting never send one. The echo is merged into
    the last known payload so the other fields (RSSI, Last Seen) survive; a
    status confirmation from the actuator later overwrites it with the real
    value.
    """
    if command not in ("ON", "OFF") or not mqtt_handler:
        return
    state = dict(mqtt_handler.get_last_state(device_name) or {})
    state["state"] = command
    await mqtt_handler.publish_state(device_name, state)


async def _echo_light_state(device_name: str, command: str, brightness: int = None):
    """Same idea as _echo_switch_state, for dimmers.

    A light entity is not optimistic either, so until the actuator reports
    back, Home Assistant keeps showing the previous value — the lamp obeys the
    command while the entity still reads 18%. Eltako dimmers do report, but
    only after a moment, and a lost telegram leaves the stale value standing
    forever. Echoing the commanded state closes that window; the actuator's
    own status overwrites it as soon as it arrives.

    brightness is 0-100 to match brightness_scale in the discovery config.
    """
    if not mqtt_handler:
        return
    state = dict(mqtt_handler.get_last_state(device_name) or {})
    state["state"] = command
    if command == "OFF":
        state["brightness"] = 0
    elif brightness is not None:
        state["brightness"] = brightness
    await mqtt_handler.publish_state(device_name, state)


async def _handle_device_command(device_name: str, payload: str, entity: str = None):
    """Handle MQTT command for an actuator device — send F6 telegram.

    For Eltako actuators (FD62NPN, FSR61, FSB61, etc.):
    - ON: F6 rocker BI (0x50) press + release
    - OFF: F6 rocker BO (0x70) press + release

    Note that an actuator's own confirmation telegram uses the opposite
    convention (0x70 = ON), see the switch branch in serial_handler.
    """
    global serial_handler, device_manager, mqtt_handler

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

    # --- EEP first, role second -------------------------------------------
    # D2-01-xx modules (NodOn SIN-2-x, in-wall relays/dimmers) are VLD devices
    # and only react to addressed "Actuator Set Output" telegrams. Branch on
    # the EEP BEFORE the role, otherwise a D2-01 registered as "light" fell
    # into the Eltako A5-38-08 path and nothing happened physically (#23).
    is_d2_01 = device.rorg.upper() == "D2" and str(device.func).zfill(2) == "01"
    if is_d2_01:
        channel = int(getattr(device, "channel", 0) or 0)
        # ON/OFF from a switch role, brightness 0-100 from a light role —
        # send_d2_01_command maps all of them to the output value.
        await serial_handler.send_d2_01_command(
            sender_id, destination, command, channel=channel
        )
        logger.info(f"Sent D2-01 {command} (channel {channel}) to {device_name}")
        if device.actuator_type == "switch":
            await _echo_switch_state(device_name, command)
        return

    if device.actuator_type == "light":
        # Dimmers use A5-38-08 Central Command Dimming
        # With on_command_type=brightness, HA sends brightness (0-100) for ON,
        # "OFF" for off. "ON" text only from manual MQTT publish.
        if command == "ON":
            # Turn on at stored brightness (dim_mode=0)
            await serial_handler.send_a5_dimmer_command(sender_id, "ON")
            logger.info(f"Sent ON (A5-38-08 stored brightness) to {device_name}")
            await _echo_light_state(device_name, "ON")
        elif command == "OFF":
            await serial_handler.send_a5_dimmer_command(sender_id, "OFF")
            logger.info(f"Sent OFF (A5-38-08) to {device_name}")
            await _echo_light_state(device_name, "OFF")
        else:
            # Brightness value from HA (0-100) — send as 0-100 directly
            # Eltako dimmers use 0-100 range (not standard 0-255)
            try:
                val = int(command)
                dim = max(0, min(100, val))
                if dim == 0:
                    await serial_handler.send_a5_dimmer_command(sender_id, "OFF")
                    logger.info(f"Sent OFF (A5-38-08 brightness=0) to {device_name}")
                    await _echo_light_state(device_name, "OFF")
                else:
                    # DIM mode: dim_mode=1 (use DB2 value) — actually sets brightness
                    await serial_handler.send_a5_dimmer_command(sender_id, "DIM", dim_value=dim)
                    logger.info(f"Sent DIM (A5-38-08 dim={dim}, {val}%) to {device_name}")
                    await _echo_light_state(device_name, "ON", brightness=dim)
            except ValueError:
                logger.warning(f"Unknown command '{command}' for dimmer {device_name}")

    elif device.actuator_type == "switch":
        # D2-01 switches are handled above (EEP branch). Everything left here
        # is an Eltako-style actuator driven by simulated F6 rocker presses.
        if command == "ON":
            # F6 Rocker BI pressed: data=0x50, status=0x30 (T21+NU)
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
            # F6 Rocker BO pressed: data=0x70, status=0x30 (T21+NU)
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

        await _echo_switch_state(device_name, command)

    elif device.actuator_type == "cover":
        # D2-05-xx blind actuators (e.g. NodOn SIN-2-RS-01) speak structured
        # VLD (RORG D2) commands, NOT F6 rocker presses. Branch on the
        # configured EEP so Eltako/RPS covers keep the rocker-simulation path.
        is_d2_05 = device.rorg.upper() == "D2" and str(device.func).zfill(2) == "05"

        if is_d2_05:
            # Position slider: entity == "position", payload is 0..100 (HA)
            if entity == "position":
                try:
                    ha_pos = int(float(command))
                except ValueError:
                    logger.warning(f"Invalid position '{command}' for {device_name}")
                    return
                await serial_handler.send_d2_05_command(
                    sender_id, destination, "POSITION", ha_position=ha_pos,
                    invert=device.invert
                )
                logger.info(f"Sent D2-05 position={ha_pos}% to {device_name}"
                            f"{' (inverted)' if device.invert else ''}")
            elif command in ("OPEN", "CLOSE", "STOP"):
                await serial_handler.send_d2_05_command(
                    sender_id, destination, command, invert=device.invert
                )
                logger.info(f"Sent D2-05 {command} to {device_name}"
                            f"{' (inverted)' if device.invert else ''}")
            else:
                logger.warning(f"Unknown cover command '{command}' for {device_name}")
            return

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
