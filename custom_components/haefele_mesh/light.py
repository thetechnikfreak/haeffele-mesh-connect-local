"""Support for Häfele Mesh lights."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_RGB_to_hs,
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Häfele Mesh lights from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Add individual lights
    lights = []
    for device_name, device_info in coordinator.lights.items():
        lights.append(HaefeleMeshLight(coordinator, device_name, device_info, "lights"))

    # Add groups as lights
    for group_name, group_info in coordinator.groups.items():
        lights.append(HaefeleMeshLight(coordinator, group_name, group_info, "groups"))

    async_add_entities(lights, True)

    # Subscribe to updates
    def update_entities():
        """Update entities when new devices are discovered."""
        new_lights = []
        
        # Check for new individual lights
        for device_name, device_info in coordinator.lights.items():
            if not any(light.unique_id == f"{entry.entry_id}_lights_{device_name}" for light in lights):
                new_light = HaefeleMeshLight(coordinator, device_name, device_info, "lights")
                lights.append(new_light)
                new_lights.append(new_light)
        
        # Check for new groups
        for group_name, group_info in coordinator.groups.items():
            if not any(light.unique_id == f"{entry.entry_id}_groups_{group_name}" for light in lights):
                new_light = HaefeleMeshLight(coordinator, group_name, group_info, "groups")
                lights.append(new_light)
                new_lights.append(new_light)
        
        if new_lights:
            async_add_entities(new_lights, True)

    coordinator.subscribe(update_entities)


class HaefeleMeshLight(LightEntity):
    """Representation of a Häfele Mesh Light."""

    def __init__(self, coordinator, name: str, device_info: dict, entity_type: str):
        """Initialize the light."""
        self._coordinator = coordinator
        self._name = name
        self._device_info = device_info
        self._entity_type = entity_type
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{entity_type}_{name}"
        self._attr_name = name
        
        # Determine supported color modes based on device capabilities
        self._attr_supported_color_modes = set()
        
        # All devices support brightness
        self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
        
        # Check if device supports color temperature
        if device_info.get("supportsColorTemperature") or device_info.get("supports_ctl"):
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_min_mireds = color_temperature_kelvin_to_mired(20000)
            self._attr_max_mireds = color_temperature_kelvin_to_mired(800)
        
        # Check if device supports color
        if device_info.get("supportsColor") or device_info.get("supports_hsl"):
            self._attr_supported_color_modes.add(ColorMode.HS)
        
        # Set default color mode
        if ColorMode.HS in self._attr_supported_color_modes:
            self._attr_color_mode = ColorMode.HS
        elif ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": self._name,
            "manufacturer": "Häfele",
            "model": self._device_info.get("model", "Mesh Device"),
            "via_device": (DOMAIN, self._coordinator.entry.entry_id),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.mqtt_client and self._coordinator.mqtt_client.is_connected()

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        status = self._device_info.get("status", {})
        on_off = status.get("onOff")
        
        if isinstance(on_off, bool):
            return on_off
        elif isinstance(on_off, str):
            return on_off.lower() == "on"
        
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        status = self._device_info.get("status", {})
        lightness = status.get("lightness")
        
        if lightness is not None:
            # Convert from 0.0-1.0 to 0-255
            return int(lightness * 255)
        
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if ColorMode.HS not in self._attr_supported_color_modes:
            return None
        
        status = self._device_info.get("status", {})
        hue = status.get("hue")
        saturation = status.get("saturation")
        
        if hue is not None and saturation is not None:
            # Convert saturation from 0.0-1.0 to 0-100
            return (hue, saturation * 100)
        
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the CT color value in mireds."""
        if ColorMode.COLOR_TEMP not in self._attr_supported_color_modes:
            return None
        
        status = self._device_info.get("status", {})
        temperature = status.get("temperature")
        
        if temperature is not None:
            # Convert from Kelvin to mireds
            return color_temperature_kelvin_to_mired(temperature)
        
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)

        if hs_color is not None and ColorMode.HS in self._attr_supported_color_modes:
            # Set HSL
            hue, saturation = hs_color
            lightness = (brightness / 255.0) if brightness is not None else 1.0
            await self._coordinator.async_set_hsl(
                self._entity_type,
                self._name,
                int(hue),
                saturation / 100.0,  # Convert from 0-100 to 0.0-1.0
                lightness,
            )
            self._attr_color_mode = ColorMode.HS
        elif color_temp is not None and ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            # Set CTL
            temperature = color_temperature_mired_to_kelvin(color_temp)
            lightness = (brightness / 255.0) if brightness is not None else 1.0
            await self._coordinator.async_set_ctl(
                self._entity_type,
                self._name,
                int(temperature),
                lightness,
            )
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif brightness is not None:
            # Set brightness only
            lightness = brightness / 255.0
            await self._coordinator.async_set_lightness(
                self._entity_type,
                self._name,
                lightness,
            )
        else:
            # Just turn on
            await self._coordinator.async_set_power(
                self._entity_type,
                self._name,
                True,
            )

        # Update status optimistically
        if "status" not in self._device_info:
            self._device_info["status"] = {}
        
        self._device_info["status"]["onOff"] = True
        
        if brightness is not None:
            self._device_info["status"]["lightness"] = brightness / 255.0
        
        if hs_color is not None:
            hue, saturation = hs_color
            self._device_info["status"]["hue"] = int(hue)
            self._device_info["status"]["saturation"] = saturation / 100.0
        
        if color_temp is not None:
            self._device_info["status"]["temperature"] = color_temperature_mired_to_kelvin(color_temp)
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._coordinator.async_set_power(
            self._entity_type,
            self._name,
            False,
        )
        
        # Update status optimistically
        if "status" not in self._device_info:
            self._device_info["status"] = {}
        
        self._device_info["status"]["onOff"] = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        # The coordinator handles updates via MQTT subscriptions
        pass
