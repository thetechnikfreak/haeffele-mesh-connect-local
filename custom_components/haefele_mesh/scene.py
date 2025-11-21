"""Support for Häfele Mesh scenes."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Häfele Mesh scenes from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    scenes = []
    for scene_name, scene_info in coordinator.scenes.items():
        scenes.append(HaefeleMeshScene(coordinator, scene_name, scene_info))

    async_add_entities(scenes, True)

    # Subscribe to updates for new scenes
    def update_entities():
        """Update entities when new scenes are discovered."""
        new_scenes = []
        
        for scene_name, scene_info in coordinator.scenes.items():
            if not any(scene.unique_id == f"{entry.entry_id}_scene_{scene_name}" for scene in scenes):
                new_scene = HaefeleMeshScene(coordinator, scene_name, scene_info)
                scenes.append(new_scene)
                new_scenes.append(new_scene)
        
        if new_scenes:
            async_add_entities(new_scenes, True)

    coordinator.subscribe(update_entities)


class HaefeleMeshScene(Scene):
    """Representation of a Häfele Mesh Scene."""

    def __init__(self, coordinator, name: str, scene_info: dict):
        """Initialize the scene."""
        self._coordinator = coordinator
        self._name = name
        self._scene_info = scene_info
        self._attr_unique_id = f"{coordinator.entry.entry_id}_scene_{name}"
        self._attr_name = name

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._coordinator.entry.entry_id)},
            "name": "Häfele Mesh Gateway",
            "manufacturer": "Häfele",
            "model": "Mesh Gateway",
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.mqtt_client and self._coordinator.mqtt_client.is_connected()

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._coordinator.async_recall_scene(self._name)
        _LOGGER.info("Activated scene: %s", self._name)
