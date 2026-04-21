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
    CONF_TEAM_ID,
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


async def _fetch_teams(hass, league_id: str) -> list[dict] | None:
    """Fetch all matches for a league and return a sorted list of unique team names.

    Each entry is a dict with ``id`` (str) and ``name`` (str).
    Returns ``None`` when the request fails.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            API_URL,
            params={"compact": "true", "league_id": league_id},
            timeout=15,
        ) as response:
            if response.status != 200:
                return None
            matches = await response.json()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Error fetching team list from BSM API")
        return None

    if not isinstance(matches, list):
        return None

    seen: set[str] = set()
    teams: list[dict] = []
    for match in matches:
        for key in ("home_team_name", "away_team_name"):
            team_name = match.get(key)
            if team_name and isinstance(team_name, str) and team_name not in seen:
                seen.add(team_name)
                teams.append({"id": team_name, "name": team_name})

    teams.sort(key=lambda x: x["name"])
    return teams


class BBSVTeamtrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._leagues: list[dict] = []
        self._leagues_fetched: bool = False
        self._selected_league_id: str = ""
        self._teams: list[dict] = []
        self._teams_fetched: bool = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step: league selection."""
        errors: dict[str, str] = {}

        if user_input is not None and self._leagues_fetched:
            selected_league_id = user_input[CONF_LEAGUE_ID]
            if selected_league_id != self._selected_league_id:
                self._teams = []
                self._teams_fetched = False
            self._selected_league_id = selected_league_id
            return await self.async_step_team()

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

        if self._leagues_fetched:
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
                }
            )
        else:
            # Leagues not yet available; show an empty form so the user can
            # submit to trigger a retry without being blocked by a selector
            # with zero options.
            schema = vol.Schema({})
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_team(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the second step: team selection."""
        errors: dict[str, str] = {}

        if user_input is not None and self._teams_fetched:
            team_id = user_input[CONF_TEAM_ID]
            name = user_input.get(CONF_NAME, "").strip() or team_id

            # Prevent duplicate entries for the same league + team combination.
            await self.async_set_unique_id(
                f"{DOMAIN}_{self._selected_league_id}_{team_id}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={
                    CONF_LEAGUE_ID: self._selected_league_id,
                    CONF_TEAM_ID: team_id,
                    CONF_NAME: name,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        # Fetch the team list for the selected league; retry until successful.
        if not self._teams_fetched:
            teams = await _fetch_teams(self.hass, self._selected_league_id)
            if teams is None:
                errors["base"] = "cannot_connect"
            elif not teams:
                errors["base"] = "no_teams_found"
            else:
                self._teams_fetched = True
                self._teams = teams

        if self._teams_fetched:
            schema = vol.Schema(
                {
                    vol.Required(CONF_TEAM_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=team["id"], label=team["name"]
                                )
                                for team in self._teams
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Optional(CONF_NAME): str,
                }
            )
        else:
            schema = vol.Schema({})
        return self.async_show_form(
            step_id="team",
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
