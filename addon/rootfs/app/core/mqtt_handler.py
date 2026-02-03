"""
MQTT Handler - Manages MQTT communication and Home Assistant discovery

Includes state persistence for devices that send infrequent updates (like Kessel Staufix).
"""

import os
import json
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
        prefix: str = "enocean",
        discovery_prefix: str = "homeassistant",
        device_manager=None,
        client_id: str = "enocean_gateway",
        config_path: str = "/config/enocean",
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

        # State persistence for infrequent sensors (like Kessel Staufix)
        self._last_states: Dict[str, Dict[str, Any]] = {}
        self._states_file = os.path.join(config_path, "last_states.json")

    @property
    def is_connected(self) -> bool:
        """Returns connection status"""
        return self._connected

    async def connect(self):
        """Connect to MQTT broker"""
        self._loop = asyncio.get_event_loop()

        self._client = mqtt.Client(client_id=self.client_id)

        if self.username:
            self._client.username_pw_set(self.username, self.password)

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
        """Disconnect from MQTT broker"""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("Disconnected from MQTT broker")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        if rc == 0:
            self._connected = True
            logger.info(f"Connected to MQTT broker at {self.host}:{self.port}")

            # Subscribe to command topics
            command_topic = f"{self.prefix}/+/set"
            client.subscribe(command_topic)
            logger.debug(f"Subscribed to {command_topic}")

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

            logger.info(f"MQTT RX [{topic}] = {payload}")

            # Handle command messages
            if topic.endswith("/set"):
                # Extract device name from topic
                parts = topic.split("/")
                if len(parts) >= 2:
                    device_name = parts[-2]
                    self._handle_command(device_name, payload)

            # Call registered callbacks
            for pattern, callback in self._message_callbacks.items():
                if self._topic_matches(pattern, topic):
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            callback(topic, payload),
                            self._loop
                        )

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches pattern with wildcards"""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        if len(pattern_parts) != len(topic_parts):
            return False

        for p, t in zip(pattern_parts, topic_parts):
            if p == "+":
                continue
            if p == "#":
                return True
            if p != t:
                return False

        return True

    def _handle_command(self, device_name: str, payload: str):
        """Handle command for a device"""
        logger.info(f"Command for device {device_name}: {payload}")
        # This will be implemented to send EnOcean telegrams

    def subscribe(self, topic_pattern: str, callback: Callable):
        """Subscribe to a topic pattern with callback"""
        self._message_callbacks[topic_pattern] = callback
        if self._client and self._connected:
            self._client.subscribe(topic_pattern)

    async def publish(self, topic: str, payload: Any, retain: bool = False):
        """Publish a message"""
        if not self._client or not self._connected:
            logger.warning("MQTT not connected, message not sent")
            return

        if isinstance(payload, dict):
            payload = json.dumps(payload)

        self._client.publish(topic, payload, retain=retain)
        logger.info(f"MQTT TX [{topic}] retain={retain}")

    async def publish_state(self, device_name: str, state: Dict[str, Any]):
        """Publish device state and persist for recovery after restart"""
        topic = f"{self.prefix}/{device_name}/state"

        # Add timestamp
        state["_last_update"] = datetime.now().isoformat()

        # Persist state for recovery (only if caching enabled)
        if self.cache_states:
            self._last_states[device_name] = state
            await self._save_states()

        await self.publish(topic, state, retain=True)

    async def _save_states(self):
        """Save last known states to file for recovery after restart"""
        try:
            os.makedirs(self.config_path, exist_ok=True)
            async with aiofiles.open(self._states_file, 'w') as f:
                await f.write(json.dumps(self._last_states, indent=2))
        except Exception as e:
            logger.error(f"Failed to save states: {e}")

    async def load_persisted_states(self):
        """Load and republish last known states after restart

        This is important for sensors that send infrequently (like Kessel Staufix
        which only sends every 8-10 hours). Without this, the state would be
        unknown until the next telegram.
        """
        if not os.path.exists(self._states_file):
            logger.info("No persisted states to restore")
            return

        try:
            async with aiofiles.open(self._states_file, 'r') as f:
                content = await f.read()
                self._last_states = json.loads(content)

            logger.info(f"Loaded {len(self._last_states)} persisted device states")

            # Republish all states with retain flag
            for device_name, state in self._last_states.items():
                topic = f"{self.prefix}/{device_name}/state"
                # Mark as restored state
                state["_restored"] = True
                await self.publish(topic, state, retain=True)
                logger.debug(f"Restored state for {device_name}")

            logger.info(f"Republished {len(self._last_states)} device states")

        except Exception as e:
            logger.error(f"Failed to load persisted states: {e}")

    def get_last_state(self, device_name: str) -> Optional[Dict[str, Any]]:
        """Get last known state for a device"""
        return self._last_states.get(device_name)

    async def publish_discovery(self, device_name: str, component: str, config: Dict[str, Any]):
        """Publish Home Assistant MQTT discovery config"""
        # Build discovery topic
        unique_id = f"enocean_{device_name}_{config.get('object_id', component)}"
        discovery_topic = f"{self.discovery_prefix}/{component}/{unique_id}/config"

        # Add required fields
        config["unique_id"] = unique_id
        config["state_topic"] = f"{self.prefix}/{device_name}/state"

        # Add device info
        if self.device_manager:
            device = self.device_manager.get_device(device_name)
            if device:
                config["device"] = {
                    "identifiers": [f"enocean_{device.address}"],
                    "name": device.description or device.name,
                    "manufacturer": device.manufacturer or "EnOcean",
                    "model": device.eep_id,
                    "via_device": "enocean_gateway"
                }

        await self.publish(discovery_topic, config, retain=True)
        logger.info(f"Published discovery for {device_name}/{component}")

    async def remove_discovery(self, device_name: str, component: str, object_id: str = ""):
        """Remove Home Assistant MQTT discovery config"""
        unique_id = f"enocean_{device_name}_{object_id or component}"
        discovery_topic = f"{self.discovery_prefix}/{component}/{unique_id}/config"

        # Publish empty payload to remove
        await self.publish(discovery_topic, "", retain=True)
        logger.info(f"Removed discovery for {device_name}/{component}")

    async def publish_device_discovery(self, device_name: str, eep_profile, mapping: Dict[str, Any]):
        """Publish discovery for all entities of a device based on EEP and mapping"""
        if not eep_profile:
            return

        device = self.device_manager.get_device(device_name) if self.device_manager else None

        for field_name, field_config in mapping.items():
            component = field_config.get("component", "sensor")
            config = {
                "name": field_config.get("name", field_name),
                "object_id": field_name,
                "value_template": f"{{{{ value_json.{field_name} }}}}"
            }

            # Add optional fields
            if "device_class" in field_config:
                config["device_class"] = field_config["device_class"]
            if "unit_of_measurement" in field_config:
                config["unit_of_measurement"] = field_config["unit_of_measurement"]
            if "icon" in field_config:
                config["icon"] = field_config["icon"]

            # Add command topic for controllable entities
            if component in ["switch", "light", "cover", "climate"]:
                config["command_topic"] = f"{self.prefix}/{device_name}/set"

            await self.publish_discovery(device_name, component, config)
