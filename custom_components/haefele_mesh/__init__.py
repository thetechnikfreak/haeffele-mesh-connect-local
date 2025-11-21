"""The Häfele Mesh integration."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "haefele_mesh"
PLATFORMS = [Platform.LIGHT, Platform.SCENE]

CONF_GATEWAY_TOPIC = "gateway_topic"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Häfele Mesh component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Häfele Mesh from a config entry."""
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        _LOGGER.error("paho-mqtt is not installed. Please install it.")
        return False

    gateway_topic = entry.data[CONF_GATEWAY_TOPIC]
    mqtt_host = entry.data[CONF_HOST]
    mqtt_port = entry.data[CONF_PORT]
    mqtt_username = entry.data.get("username")
    mqtt_password = entry.data.get("password")

    coordinator = HaefeleMeshCoordinator(
        hass, entry, mqtt_host, mqtt_port, gateway_topic, mqtt_username, mqtt_password
    )
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Connect to MQTT
    await coordinator.async_connect()

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Disconnect from MQTT
    await coordinator.async_disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HaefeleMeshCoordinator:
    """Coordinator for Häfele Mesh."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        mqtt_host: str,
        mqtt_port: int,
        gateway_topic: str,
        mqtt_username: str | None = None,
        mqtt_password: str | None = None,
    ):
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.gateway_topic = gateway_topic
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.mqtt_client = None
        self.lights = {}
        self.groups = {}
        self.scenes = {}
        self._listeners = []

    async def async_connect(self):
        """Connect to MQTT broker."""
        import paho.mqtt.client as mqtt

        def on_connect(client, userdata, flags, rc):
            """Handle MQTT connection."""
            if rc == 0:
                _LOGGER.info("Connected to MQTT broker at %s:%s", self.mqtt_host, self.mqtt_port)
                # Subscribe to discovery topics
                client.subscribe(f"{self.gateway_topic}/lights")
                client.subscribe(f"{self.gateway_topic}/groups")
                client.subscribe(f"{self.gateway_topic}/scenes")
                # Subscribe to status updates
                client.subscribe(f"{self.gateway_topic}/lights/+/status")
                client.subscribe(f"{self.gateway_topic}/groups/+/status")
            else:
                _LOGGER.error("Failed to connect to MQTT broker, return code %s", rc)

        def on_message(client, userdata, msg):
            """Handle incoming MQTT messages."""
            self.hass.loop.call_soon_threadsafe(
                self._handle_message, msg.topic, msg.payload.decode()
            )

        self.mqtt_client = mqtt.Client()
        
        # Set authentication if provided
        if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            _LOGGER.info("MQTT authentication configured for user: %s", self.mqtt_username)
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message

        # Connect in executor to avoid blocking
        await self.hass.async_add_executor_job(
            self.mqtt_client.connect, self.mqtt_host, self.mqtt_port, 60
        )
        await self.hass.async_add_executor_job(self.mqtt_client.loop_start)

    async def async_disconnect(self):
        """Disconnect from MQTT broker."""
        if self.mqtt_client:
            await self.hass.async_add_executor_job(self.mqtt_client.loop_stop)
            await self.hass.async_add_executor_job(self.mqtt_client.disconnect)

    def _handle_message(self, topic: str, payload: str):
        """Handle incoming MQTT message."""
        try:
            data = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            _LOGGER.error("Failed to parse JSON from topic %s: %s", topic, payload)
            return

        _LOGGER.debug("Received MQTT message on topic %s: %s", topic, data)

        # Handle discovery messages
        if topic == f"{self.gateway_topic}/lights":
            self._handle_lights_discovery(data)
        elif topic == f"{self.gateway_topic}/groups":
            self._handle_groups_discovery(data)
        elif topic == f"{self.gateway_topic}/scenes":
            self._handle_scenes_discovery(data)
        # Handle status updates
        elif "/status" in topic:
            self._handle_status_update(topic, data)

        # Notify listeners
        for listener in self._listeners:
            listener()

    def _handle_lights_discovery(self, lights: list):
        """Handle lights discovery."""
        if not lights:
            return
        
        for light in lights:
            device_name = light.get("name")
            if device_name:
                self.lights[device_name] = light
                _LOGGER.info("Discovered light: %s", device_name)

    def _handle_groups_discovery(self, groups: list):
        """Handle groups discovery."""
        if not groups:
            return
        
        for group in groups:
            group_name = group.get("name")
            if group_name:
                self.groups[group_name] = group
                _LOGGER.info("Discovered group: %s", group_name)

    def _handle_scenes_discovery(self, scenes: list):
        """Handle scenes discovery."""
        if not scenes:
            return
        
        for scene in scenes:
            scene_name = scene.get("name")
            if scene_name:
                self.scenes[scene_name] = scene
                _LOGGER.info("Discovered scene: %s", scene_name)

    def _handle_status_update(self, topic: str, data: dict):
        """Handle status update."""
        parts = topic.split("/")
        
        if "lights" in parts:
            idx = parts.index("lights")
            if idx + 1 < len(parts):
                device_name = parts[idx + 1]
                if device_name in self.lights:
                    self.lights[device_name]["status"] = data
                    _LOGGER.debug("Updated light %s status: %s", device_name, data)
        elif "groups" in parts:
            idx = parts.index("groups")
            if idx + 1 < len(parts):
                group_name = parts[idx + 1]
                if group_name in self.groups:
                    self.groups[group_name]["status"] = data
                    _LOGGER.debug("Updated group %s status: %s", group_name, data)

    def subscribe(self, listener):
        """Subscribe to updates."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def publish(self, topic: str, payload: Any):
        """Publish MQTT message."""
        if self.mqtt_client and self.mqtt_client.is_connected():
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            self.mqtt_client.publish(topic, payload)
        else:
            _LOGGER.error("MQTT client not connected")

    async def async_set_power(self, entity_type: str, name: str, state: bool):
        """Set power state."""
        topic = f"{self.gateway_topic}/{entity_type}/{name}/power"
        payload = {"onOff": "on" if state else "off"}
        await self.hass.async_add_executor_job(self.publish, topic, payload)

    async def async_set_lightness(self, entity_type: str, name: str, lightness: float):
        """Set lightness (0.0 to 1.0)."""
        topic = f"{self.gateway_topic}/{entity_type}/{name}/lightness"
        payload = {"lightness": lightness}
        await self.hass.async_add_executor_job(self.publish, topic, payload)

    async def async_set_hsl(self, entity_type: str, name: str, hue: int, saturation: float, lightness: float):
        """Set HSL values."""
        topic = f"{self.gateway_topic}/{entity_type}/{name}/hsl"
        payload = {
            "hue": hue,
            "saturation": saturation,
            "lightness": lightness
        }
        await self.hass.async_add_executor_job(self.publish, topic, payload)

    async def async_set_ctl(self, entity_type: str, name: str, temperature: int, lightness: float):
        """Set color temperature and lightness."""
        topic = f"{self.gateway_topic}/{entity_type}/{name}/ctl"
        payload = {
            "temperature": temperature,
            "lightness": lightness
        }
        await self.hass.async_add_executor_job(self.publish, topic, payload)

    async def async_recall_scene(self, scene_name: str, target_type: str = None, target_name: str = None):
        """Recall a scene."""
        if target_type and target_name:
            # Recall scene for specific device or group
            topic = f"{self.gateway_topic}/{target_type}/{target_name}/recallScene"
        else:
            # Recall scene globally
            topic = f"{self.gateway_topic}/scenes/recallScene"
        
        payload = scene_name
        await self.hass.async_add_executor_job(self.publish, topic, payload)
