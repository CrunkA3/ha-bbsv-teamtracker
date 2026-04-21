"""Config flow for BBSV Teamtracker integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_URL,
    CONF_LEAGUE_ID,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _fetch_leagues(hass) -> list[dict] | None:
    """Fetch all matches and return a sorted list of unique leagues.

    Each entry is a dict with ``id`` (str) and ``name`` (str).
    Returns ``None`` when the request fails.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            API_URL, params={"compact": "true"}, timeout=15
        ) as response:
            if response.status != 200:
                return None
            matches = await response.json()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Error fetching league list from BSM API")
        return None

    if not isinstance(matches, list):
        return None

    seen: set[str] = set()
    leagues: list[dict] = []
    for match in matches:
        league = match.get("league")
        if not isinstance(league, dict):
            continue
        league_id = league.get("id")
        league_name = league.get("name")
        if league_id is None or not league_name:
            continue
        league_id_str = str(league_id)
        if league_id_str not in seen:
            seen.add(league_id_str)
            leagues.append({"id": league_id_str, "name": league_name})

    leagues.sort(key=lambda x: x["name"])
    return leagues


class BBSVTeamtrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._leagues: list[dict] = []
        self._leagues_fetched: bool = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            league_id = user_input[CONF_LEAGUE_ID]
            name = user_input.get(CONF_NAME, "").strip() or f"{DEFAULT_NAME} {league_id}"

            # Prevent duplicate entries for the same league ID.
            await self.async_set_unique_id(f"{DOMAIN}_{league_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={
                    CONF_LEAGUE_ID: league_id,
                    CONF_NAME: name,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        # Fetch the league list; retry on every display attempt until successful.
        if not self._leagues_fetched:
            leagues = await _fetch_leagues(self.hass)
            if leagues is None:
                errors["base"] = "cannot_connect"
            elif not leagues:
                errors["base"] = "no_leagues_found"
            else:
                self._leagues_fetched = True
                self._leagues = leagues

        schema = vol.Schema(
            {
                vol.Required(CONF_LEAGUE_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=league["id"], label=league["name"]
                            )
                            for league in self._leagues
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_NAME): str,
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
