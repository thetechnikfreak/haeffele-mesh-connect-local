"""Config flow for Häfele Mesh integration."""
from __future__ import annotations

import logging
import secrets
import string
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_GATEWAY_TOPIC, CONF_PASSWORD, CONF_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


def generate_password(length: int = 32) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def validate_manual_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate manual MQTT configuration."""
    try:
        import paho.mqtt.client as mqtt_client
        
        client = mqtt_client.Client()
        
        # Set authentication if provided
        if data.get(CONF_USERNAME) and data.get(CONF_PASSWORD):
            client.username_pw_set(data[CONF_USERNAME], data[CONF_PASSWORD])
        
        await hass.async_add_executor_job(
            client.connect, data[CONF_HOST], data[CONF_PORT], 10
        )
        await hass.async_add_executor_job(client.disconnect)
        
        return {"title": f"Häfele Mesh ({data[CONF_HOST]})"}
    except Exception as err:
        _LOGGER.error("Could not connect to MQTT broker: %s", err)
        raise CannotConnect from err


async def create_mosquitto_user(hass: HomeAssistant, username: str, password: str) -> bool:
    """Create a user in Mosquitto broker via Home Assistant MQTT integration."""
    try:
        # Call the MQTT service to create user
        await hass.services.async_call(
            "mqtt",
            "create_user",
            {"username": username, "password": password},
            blocking=True,
        )
        return True
    except Exception as err:
        _LOGGER.warning("Could not create MQTT user automatically: %s", err)
        return False


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Häfele Mesh."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._setup_type = None
        self._generated_username = None
        self._generated_password = None
        self._mqtt_config = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup type selection."""
        if user_input is not None:
            self._setup_type = user_input["setup_type"]
            
            if self._setup_type == "automatic":
                return await self.async_step_automatic()
            else:
                return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("setup_type", default="automatic"): vol.In({
                    "automatic": "Automatic (Mosquitto Add-on)",
                    "manual": "Manual MQTT Configuration"
                })
            }),
        )

    async def async_step_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle automatic setup with Mosquitto."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Generate credentials
            username = "haefele_mesh"
            password = generate_password()
            
            # Try to create user in Mosquitto
            user_created = await create_mosquitto_user(self.hass, username, password)
            
            if not user_created:
                _LOGGER.warning("Could not auto-create user, showing manual instructions")
            
            # Store the configuration
            config_data = {
                CONF_HOST: "localhost",
                CONF_PORT: 1883,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_GATEWAY_TOPIC: user_input.get(CONF_GATEWAY_TOPIC, "Mesh"),
            }
            
            # Store credentials for display
            self._generated_username = username
            self._generated_password = password
            self._mqtt_config = config_data
            
            # Show credentials to user
            return await self.async_step_show_credentials()

        return self.async_show_form(
            step_id="automatic",
            data_schema=vol.Schema({
                vol.Required(CONF_GATEWAY_TOPIC, default="Mesh"): str,
            }),
            description_placeholders={
                "info": "A secure user will be created automatically in Mosquitto."
            },
        )

    async def async_step_show_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show generated credentials to user."""
        if user_input is not None:
            # Create the config entry
            await self.async_set_unique_id(
                f"localhost_{self._mqtt_config[CONF_GATEWAY_TOPIC]}"
            )
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title="Häfele Mesh (Mosquitto)",
                data=self._mqtt_config,
            )

        # Get local IP for display
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "YOUR_HOME_ASSISTANT_IP"

        return self.async_show_form(
            step_id="show_credentials",
            data_schema=vol.Schema({}),
            description_placeholders={
                "broker_url": f"mqtt://{local_ip}:1883",
                "username": self._generated_username,
                "password": self._generated_password,
                "topic": self._mqtt_config[CONF_GATEWAY_TOPIC],
                "instructions": (
                    "⚠️ IMPORTANT: Save these credentials now!\n\n"
                    "Enter these details in your Häfele Mesh Connect app:\n\n"
                    f"• MQTT Broker: mqtt://{local_ip}:1883\n"
                    f"• Username: {self._generated_username}\n"
                    f"• Password: {self._generated_password}\n"
                    f"• Topic: {self._mqtt_config[CONF_GATEWAY_TOPIC]}\n\n"
                    "Click Submit when you have saved these credentials."
                )
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual MQTT configuration."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_manual_input(self.hass, user_input)
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
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default="localhost"): str,
                vol.Required(CONF_PORT, default=1883): cv.port,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Required(CONF_GATEWAY_TOPIC, default="Mesh"): str,
            }),
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
