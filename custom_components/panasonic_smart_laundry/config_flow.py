"""Config flow for Panasonic Smart Laundry."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PanasonicApiError, PanasonicAuthError, PanasonicSmartLaundryApi
from .const import (
    CONF_APPLIANCE_ID,
    CONF_COM_ID,
    DEFAULT_COM_ID,
    DOMAIN,
    SUPPORTED_COM_IDS,
)

logger = logging.getLogger(__name__)

_MODEL_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_COM_ID,
            default=DEFAULT_COM_ID,
        ): vol.In({com_id: com_id for com_id in SUPPORTED_COM_IDS}),
    }
)


class PanasonicSmartLaundryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Panasonic Smart Laundry."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._login: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect account credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = PanasonicSmartLaundryApi(
                session,
                user_input["username"],
                user_input["password"],
            )
            try:
                await api.login()
                profile = await api.get_user_profile()
            except PanasonicAuthError:
                errors["base"] = "invalid_auth"
            except PanasonicApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            else:
                appliance_id = (profile.get("selected_device") or {}).get(
                    "appliance_id"
                )
                if not appliance_id:
                    errors["base"] = "no_appliance"
                else:
                    self._login = {
                        "username": user_input["username"],
                        "password": user_input["password"],
                        CONF_APPLIANCE_ID: appliance_id,
                        "access_token": api.access_token,
                        "refresh_token": api.refresh_token,
                        "token_expires_at": api.token_expires_at,
                    }
                    return await self.async_step_model()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the washing machine model by COM_ID."""
        if self._login is None:
            return await self.async_step_user()

        errors: dict[str, str] = {}

        if user_input is not None:
            com_id = user_input[CONF_COM_ID]
            if com_id not in SUPPORTED_COM_IDS:
                errors["base"] = "invalid_model"
            else:
                appliance_id = self._login[CONF_APPLIANCE_ID]
                await self.async_set_unique_id(appliance_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=com_id,
                    data={
                        "username": self._login["username"],
                        "password": self._login["password"],
                        CONF_COM_ID: com_id,
                        CONF_APPLIANCE_ID: appliance_id,
                        "access_token": self._login["access_token"],
                        "refresh_token": self._login["refresh_token"],
                        "token_expires_at": self._login["token_expires_at"],
                    },
                )

        return self.async_show_form(
            step_id="model",
            data_schema=_MODEL_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        username = entry.data["username"]
        password = entry.data["password"]

        if user_input is not None:
            password = user_input["password"]
            session = async_get_clientsession(self.hass)
            api = PanasonicSmartLaundryApi(session, username, password)
            try:
                await api.login()
            except PanasonicAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                logger.exception("Unexpected error during reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        "password": password,
                        "access_token": api.access_token,
                        "refresh_token": api.refresh_token,
                        "token_expires_at": api.token_expires_at,
                    },
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            errors=errors,
        )
