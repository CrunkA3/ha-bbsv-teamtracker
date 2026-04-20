"""Config flow for BBSV Teamtracker integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BASE_URL,
    CONF_LEAGUE_ID,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import _parse_table

_LOGGER = logging.getLogger(__name__)


async def _validate_league(hass, league_id: str) -> list | None:
    """Try to fetch the league table and return parsed rows or None on error."""
    url = f"{BASE_URL}?bsm_league={league_id}"
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200:
                return None
            html = await response.text()
    except Exception:  # noqa: BLE001
        return None
    return _parse_table(html)


class BBSVTeamtrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            league_id = user_input[CONF_LEAGUE_ID].strip()
            name = user_input.get(CONF_NAME, "").strip() or f"{DEFAULT_NAME} {league_id}"

            # Prevent duplicate entries for the same league ID.
            await self.async_set_unique_id(f"{DOMAIN}_{league_id}")
            self._abort_if_unique_id_configured()

            teams = await _validate_league(self.hass, league_id)
            if teams is None:
                errors["base"] = "cannot_connect"
            elif not teams:
                errors[CONF_LEAGUE_ID] = "empty_table"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_LEAGUE_ID: league_id,
                        CONF_NAME: name,
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_LEAGUE_ID): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return BBSVTeamtrackerOptionsFlow(config_entry)


class BBSVTeamtrackerOptionsFlow(OptionsFlow):
    """Handle options (e.g. update interval) for an existing entry."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval: int = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    int, vol.Range(min=60)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
