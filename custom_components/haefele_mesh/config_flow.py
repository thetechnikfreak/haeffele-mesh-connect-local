"""Config flow for Häfele Mesh integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_GATEWAY_TOPIC, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="localhost"): str,
        vol.Required(CONF_PORT, default=1883): cv.port,
        vol.Required(CONF_GATEWAY_TOPIC, default="haefele/gateway"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Try to connect to MQTT broker
    try:
        import paho.mqtt.client as mqtt
        
        client = mqtt.Client()
        result = await hass.async_add_executor_job(
            client.connect, data[CONF_HOST], data[CONF_PORT], 10
        )
        await hass.async_add_executor_job(client.disconnect)
        
        return {"title": f"Häfele Mesh ({data[CONF_HOST]})"}
    except Exception as err:
        _LOGGER.error("Could not connect to MQTT broker: %s", err)
        raise CannotConnect from err


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Häfele Mesh."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create a unique ID based on host and gateway topic
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}_{user_input[CONF_GATEWAY_TOPIC]}"
                )
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
