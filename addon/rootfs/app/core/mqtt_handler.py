"""
MQTT Handler - Manages MQTT communication and Home Assistant discovery

Compatible with ChristopheHD/HA_enoceanmqtt-addon MQTT topic patterns.
Includes state persistence for devices that send infrequent updates.

MQTT Topic Structure:
    {prefix}/{device_name}/state        - Device state (JSON, retained)
    {prefix}/{device_name}/set          - Device commands
    {prefix}/{device_name}/availability - Per-device availability (retained)
    {prefix}/__system/status            - Gateway status with LWT (retained)
    {discovery_prefix}/{component}/enocean/{uid}/config - HA discovery (retained)
"""

import os
import json
import yaml
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import paho.mqtt.client as mqtt
import aiofiles

logger = logging.getLogger(__name__)


class MQTTHandler:
    """Handles MQTT communication with Home Assistant"""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        prefix: str = "enoceanmqtt",
        discovery_prefix: str = "homeassistant",
        device_manager=None,
        client_id: str = "enocean_gateway",
        config_path: str = "/data",
        cache_states: bool = True
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.prefix = prefix.rstrip("/")
        self.discovery_prefix = discovery_prefix.rstrip("/")
        self.device_manager = device_manager
        self.client_id = client_id
        self.config_path = config_path
        self.cache_states = cache_states

        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._message_callbacks: Dict[str, Callable] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Callback for HA birth message / reconnect (re-publish all discoveries)
        self._on_ha_birth: Optional[Callable] = None

        # Callback for device commands (MQTT → EnOcean telegram)
        self._on_device_command: Optional[Callable] = None

        # State persistence for infrequent sensors (like Kessel Staufix)
        self._last_states: Dict[str, Dict[str, Any]] = {}
        self._states_file = os.path.join(config_path, "last_states.yaml")
        self._legacy_states_file = os.path.join(config_path, "last_states.json")

        # Debounced persist: instead of writing the full YAML on every
        # publish_state() (which hammers SD/flash when many sensors send
        # frequently), coalesce updates into a single write every
        # _save_interval seconds.
        self._save_dirty = False
        self._save_task: Optional[asyncio.Task] = None
        self._save_interval = 10.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def gateway_status_topic(self) -> str:
        return f"{self.prefix}/__system/status"

    def set_ha_birth_callback(self, callback: Callable):
        """Set callback for when HA sends birth message or MQTT reconnects.
        The callback should re-publish all discoveries and availability.
        """
        self._on_ha_birth = callback

    def set_device_command_callback(self, callback: Callable):
        """Set callback for device commands received via MQTT.
        Callback signature: async def handler(device_name, payload, entity)
        """
        self._on_device_command = callback

    async def connect(self):
        """Connect to MQTT broker with LWT (Last Will and Testament)"""
        self._loop = asyncio.get_event_loop()

        self._client = mqtt.Client(client_id=self.client_id)

        if self.username:
            self._client.username_pw_set(self.username, self.password)

        # Set Last Will - published automatically on unexpected disconnect
        self._client.will_set(
            self.gateway_status_topic,
            payload="offline",
            qos=1,
            retain=True
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        try:
            self._client.connect_async(self.host, self.port)
            self._client.loop_start()

            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self._connected:
                    break
                await asyncio.sleep(0.1)

            if not self._connected:
                logger.warning("MQTT connection timeout - will retry in background")

        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    async def disconnect(self):
        """Disconnect gracefully - publish offline status for all devices first"""
        # Flush any pending state writes before we lose the event loop
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass

        if self._client and self._connected:
            # Publish offline for all configured devices
            if self.device_manager:
                for device_name in self.device_manager.devices:
                    avail_topic = f"{self.prefix}/{device_name}/availability"
                    self._client.publish(avail_topic, "offline", qos=1, retain=True)

            # Publish gateway offline
            self._client.publish(self.gateway_status_topic, "offline", qos=1, retain=True)

            # Small delay to ensure messages are sent before disconnect
            await asyncio.sleep(0.5)

            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("Disconnected from MQTT broker (published offline status)")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback - called on initial connect and reconnects"""
        if rc == 0:
            self._connected = True
            logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")

            # Publish gateway online status
            client.publish(self.gateway_status_topic, "online", qos=1, retain=True)

            # Subscribe to command topics
            client.subscribe(f"{self.prefix}/+/set", qos=1)
            client.subscribe(f"{self.prefix}/+/set/#", qos=1)
            logger.debug(f"Subscribed to {self.prefix}/+/set[/#]")

            # Subscribe to HA birth message for re-publishing discoveries
            ha_status_topic = f"{self.discovery_prefix}/status"
            client.subscribe(ha_status_topic, qos=1)
            logger.info(f"Subscribed to HA birth message: {ha_status_topic}")

            # On reconnect, re-publish all discoveries
            if self._on_ha_birth and self._loop:
                asyncio.run_coroutine_threadsafe(self._on_ha_birth(), self._loop)

        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT connection lost (rc={rc}), will reconnect")

    def _on_message(self, client, userdata, message):
        """MQTT message callback"""
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')

            logger.debug(f"MQTT RX [{topic}] = {payload}")

            # Handle HA birth message - re-publish all discoveries
            if topic == f"{self.discovery_prefix}/status" and payload == "online":
                logger.info("HA birth message received - re-publishing all discoveries")
                if self._on_ha_birth and self._loop:
                    asyncio.run_coroutine_threadsafe(self._on_ha_birth(), self._loop)
                return

            # Handle command messages: {prefix}/{device_name}/set[/{entity}]
            prefix_with_slash = f"{self.prefix}/"
            if topic.startswith(prefix_with_slash) and "/set" in topic:
                remainder = topic[len(prefix_with_slash):]
                parts = remainder.split("/")
                if len(parts) >= 2 and parts[1] == "set":
                    device_name = parts[0]
                    entity = parts[2] if len(parts) > 2 else None
                    self._handle_command(device_name, payload, entity)

            # Call registered callbacks
            for pattern, callback in list(self._message_callbacks.items()):
                if self._topic_matches(pattern, topic):
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            callback(topic, payload),
                            self._loop
                        )

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches pattern with MQTT wildcards (+ and #)"""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        for i, p in enumerate(pattern_parts):
            if p == "#":
                return True  # # matches everything from here
            if i >= len(topic_parts):
                return False
            if p == "+":
                continue  # + matches single level
            if p != topic_parts[i]:
                return False

        return len(pattern_parts) == len(topic_parts)

    def _handle_command(self, device_name: str, payload: str, entity: str = None):
        """Handle command for a device — dispatch to serial handler for actuators"""
        target = f"{device_name}/{entity}" if entity else device_name
        logger.info(f"Command for {target}: {payload}")

        if self._on_device_command and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._on_device_command(device_name, payload, entity),
                self._loop
            )

    def subscribe(self, topic_pattern: str, callback: Callable):
        """Subscribe to a topic pattern with callback"""
        self._message_callbacks[topic_pattern] = callback
        if self._client and self._connected:
            self._client.subscribe(topic_pattern, qos=1)

    async def publish(self, topic: str, payload: Any, retain: bool = False, qos: int = 1):
        """Publish a message"""
        if not self._client or not self._connected:
            logger.warning(f"MQTT not connected, message not sent: {topic}")
            return

        if isinstance(payload, dict):
            payload = json.dumps(payload)

        self._client.publish(topic, payload, qos=qos, retain=retain)
        logger.debug(f"MQTT TX [{topic}] retain={retain} qos={qos}")

    async def publish_device_availability(self, device_name: str, available: bool = True):
        """Publish per-device availability"""
        topic = f"{self.prefix}/{device_name}/availability"
        payload = "online" if available else "offline"
        await self.publish(topic, payload, retain=True, qos=1)

    async def publish_state(self, device_name: str, state: Dict[str, Any]):
        """Publish device state and persist for recovery after restart"""
        topic = f"{self.prefix}/{device_name}/state"

        # Add timestamp
        state["_last_update"] = datetime.now().isoformat()

        # Persist state for recovery (only if caching enabled).
        # Writes are debounced: updates just mark the cache dirty and a
        # single background task flushes the full YAML every _save_interval.
        if self.cache_states:
            self._last_states[device_name] = state
            self._save_dirty = True
            if self._save_task is None or self._save_task.done():
                self._save_task = asyncio.create_task(self._debounced_save())

        await self.publish(topic, state, retain=True)

    async def _debounced_save(self):
        """Wait out the debounce window, then flush dirty states to disk.

        Cancelled by disconnect() — if dirty at cancel time we flush
        synchronously so we don't lose data on shutdown.
        """
        try:
            await asyncio.sleep(self._save_interval)
            if self._save_dirty:
                self._save_dirty = False
                await self._save_states()
        except asyncio.CancelledError:
            if self._save_dirty:
                self._save_dirty = False
                try:
                    await self._save_states()
                except Exception as e:
                    logger.error(f"Failed to flush states on shutdown: {e}")
            raise

    async def _save_states(self):
        """Save last known states to file for recovery after restart"""
        try:
            os.makedirs(self.config_path, exist_ok=True)
            async with aiofiles.open(self._states_file, 'w') as f:
                await f.write(yaml.dump(self._last_states, default_flow_style=False, allow_unicode=True))
        except Exception as e:
            logger.error(f"Failed to save states: {e}")

    async def load_persisted_states(self):
        """Load last known states from file into memory.

        Important for sensors that send infrequently (like Kessel Staufix
        which only sends every 8-10 hours).

        NOTE: This only loads into memory. Call republish_cached_states()
        AFTER discovery configs are published to ensure HA evaluates states
        with the correct entity configuration (e.g., payload_on/payload_off).
        """
        # One-time migration from JSON to YAML
        if not os.path.exists(self._states_file) and os.path.exists(self._legacy_states_file):
            try:
                async with aiofiles.open(self._legacy_states_file, 'r') as f:
                    self._last_states = json.loads(await f.read())
                await self._save_states()
                logger.info("Migrated last_states.json -> last_states.yaml")
                return
            except Exception as e:
                logger.error(f"Failed to migrate last_states.json: {e}")

        if not os.path.exists(self._states_file):
            logger.info("No persisted states to restore")
            return

        try:
            async with aiofiles.open(self._states_file, 'r') as f:
                content = await f.read()
                self._last_states = yaml.safe_load(content) or {}

            logger.info(f"Loaded {len(self._last_states)} persisted device states into memory")

        except Exception as e:
            logger.error(f"Failed to load persisted states: {e}")

    async def republish_cached_states(self):
        """Publish all cached states to MQTT.

        Must be called AFTER discovery configs are published, so that HA
        evaluates the state values with the correct entity configuration
        (e.g., binary_sensor payload_on/payload_off).
        """
        if not self._last_states:
            return

        for device_name, state in self._last_states.items():
            topic = f"{self.prefix}/{device_name}/state"
            state["_restored"] = True
            await self.publish(topic, state, retain=True)
            logger.debug(f"Restored state for {device_name}")

        logger.info(f"Republished {len(self._last_states)} cached device states")

    def get_last_state(self, device_name: str) -> Optional[Dict[str, Any]]:
        """Get last known state for a device"""
        return self._last_states.get(device_name)

    async def publish_discovery_config(self, component: str, unique_id: str, config: Dict[str, Any]):
        """Publish a single HA MQTT discovery config"""
        discovery_topic = f"{self.discovery_prefix}/{component}/enocean/{unique_id}/config"
        await self.publish(discovery_topic, config, retain=True)
        logger.debug(f"Published discovery: {discovery_topic}")

    async def remove_discovery_config(self, component: str, unique_id: str):
        """Remove HA discovery config by publishing empty payload"""
        discovery_topic = f"{self.discovery_prefix}/{component}/enocean/{unique_id}/config"
        await self.publish(discovery_topic, "", retain=True)
        logger.info(f"Removed discovery: {discovery_topic}")
