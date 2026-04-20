"""DataUpdateCoordinator for BBSV Teamtracker."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_URL,
    CONF_LEAGUE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _compute_standings(matches: list[dict]) -> list[dict]:
    """Compute a standings table from a list of BSM match dicts.

    Only matches where both ``home_runs`` and ``away_runs`` are numeric values
    (i.e. the game has been played and scored) are counted.

    Returns a list of team dicts with canonical keys:
    position, team, games, wins, losses, runs_for, runs_against, run_diff,
    points – sorted by points (desc) then run_diff (desc).
    """
    standings: dict[str, dict] = {}

    for match in matches:
        home_runs = match.get("home_runs")
        away_runs = match.get("away_runs")

        # Skip matches that have not been played / scored yet.
        if not isinstance(home_runs, (int, float)) or not isinstance(away_runs, (int, float)):
            continue

        home_name: str = match.get("home_team_name") or ""
        away_name: str = match.get("away_team_name") or ""
        if not home_name or not away_name:
            continue

        for name in (home_name, away_name):
            if name not in standings:
                standings[name] = {
                    "team": name,
                    "games": 0,
                    "wins": 0,
                    "losses": 0,
                    "runs_for": 0,
                    "runs_against": 0,
                }

        standings[home_name]["games"] += 1
        standings[away_name]["games"] += 1
        standings[home_name]["runs_for"] += int(home_runs)
        standings[home_name]["runs_against"] += int(away_runs)
        standings[away_name]["runs_for"] += int(away_runs)
        standings[away_name]["runs_against"] += int(home_runs)

        if home_runs > away_runs:
            standings[home_name]["wins"] += 1
            standings[away_name]["losses"] += 1
        elif away_runs > home_runs:
            standings[away_name]["wins"] += 1
            standings[home_name]["losses"] += 1
        # Tied games (e.g. called due to weather) count towards games played
        # but award no win, no loss, and no points to either side.

    table: list[dict] = []
    for entry in standings.values():
        entry["run_diff"] = entry["runs_for"] - entry["runs_against"]
        entry["points"] = entry["wins"] * 2
        table.append(entry)

    table.sort(key=lambda e: (-e["points"], -e["run_diff"]))
    for position, entry in enumerate(table, 1):
        entry["position"] = position

    return table


class BBSVTeamtrackerCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches match data from the BSM API and computes standings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._league_id: str = entry.data[CONF_LEAGUE_ID]
        scan_interval: int = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._league_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def league_id(self) -> str:
        """Return the configured league ID."""
        return self._league_id

    async def _async_update_data(self) -> list[dict]:
        """Fetch match data from the BSM API and return computed standings."""
        params = {"compact": "true", "league_id": self._league_id}
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(API_URL, params=params, timeout=30) as response:
                response.raise_for_status()
                matches: list[dict] = await response.json()
        except Exception as exc:
            raise UpdateFailed(
                f"Error fetching BSM match data for league {self._league_id}: {exc}"
            ) from exc

        if not isinstance(matches, list):
            raise UpdateFailed(
                f"Unexpected response format from BSM API for league {self._league_id}"
            )

        standings = _compute_standings(matches)
        if not standings:
            _LOGGER.warning(
                "No standings could be computed for BSM league %s "
                "(no completed matches found)",
                self._league_id,
            )
        return standings
