"""DataUpdateCoordinator for BBSV Teamtracker."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_URL,
    API_URL_LEAGUE,
    CONF_LEAGUE_ID,
    CONF_SCAN_INTERVAL,
    CONF_TEAM_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _compute_standings(matches: list[dict]) -> tuple[list[dict], dict[str, dict], int, int]:
    """Compute a standings table from a list of BSM match dicts.

    Only matches where both ``home_runs`` and ``away_runs`` are numeric values
    (i.e. the game has been played and scored) are counted.

    Returns a tuple of:
    - list of team dicts with canonical keys:
      position, team, games, wins, losses, runs_for, runs_against, run_diff,
      points – sorted by points (desc) then run_diff (desc).
    - total home runs across all completed matches
    - total away runs across all completed matches
    """
    standings: dict[str, dict] = {}
    total_home_runs: int = 0
    total_away_runs: int = 0

    for match in matches:
        home_runs = match.get("home_runs")
        away_runs = match.get("away_runs")

        # Skip matches that have not been played / scored yet.
        if not isinstance(home_runs, (int, float)) or not isinstance(away_runs, (int, float)):
            continue

        home_id: str = match.get("home_team_name") or ""
        away_id: str = match.get("away_team_name") or ""
        if not home_id or not away_id:
            continue

        total_home_runs += int(home_runs)
        total_away_runs += int(away_runs)

        for name in (home_id, away_id):
            if name not in standings:
                standings[name] = {
                    "team": name,
                    "games": 0,
                    "wins": 0,
                    "losses": 0,
                    "runs_for": 0,
                    "runs_against": 0,
                }

        standings[home_id]["games"] += 1
        standings[away_id]["games"] += 1
        standings[home_id]["runs_for"] += int(home_runs)
        standings[home_id]["runs_against"] += int(away_runs)
        standings[away_id]["runs_for"] += int(away_runs)
        standings[away_id]["runs_against"] += int(home_runs)

        if home_runs > away_runs:
            standings[home_id]["wins"] += 1
            standings[away_id]["losses"] += 1
        elif away_runs > home_runs:
            standings[away_id]["wins"] += 1
            standings[home_id]["losses"] += 1
        # Tied games (e.g. called due to weather) count towards games played
        # but award no win, no loss, and no points to either side.

    table: list[dict] = []
    for entry in standings.values():
        entry["run_diff"] = entry["runs_for"] - entry["runs_against"]
        entry["points"] = entry["wins"] * 2
        table.append(entry)

    table.sort(key=lambda e: (-e["points"], -e["run_diff"], -e["runs_for"], e["team"]))
    for position, entry in enumerate(table, 1):
        entry["position"] = position

    return table, standings, total_home_runs, total_away_runs


class BBSVTeamtrackerCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches match data from the BSM API and computes standings."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._league_id: str = entry.data[CONF_LEAGUE_ID]
        self._team_id: int = entry.data.get(CONF_TEAM_ID, "")
        scan_interval: int = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        self.last_updated: datetime | None = None
        self.total_home_runs: int = 0
        self.total_away_runs: int = 0
        self.team_games: int = 0
        coordinator_name = (
            f"{DOMAIN}_{self._league_id}_{self._team_id}"
            if self._team_id
            else f"{DOMAIN}_{self._league_id}"
        )
        super().__init__(
            hass,
            _LOGGER,
            name=coordinator_name,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def league_id(self) -> str:
        """Return the configured league ID."""
        return self._league_id

    @property
    def team_id(self) -> str:
        """Return the configured team name used as the team identifier."""
        return self._team_id

    async def _async_update_data(self) -> list[dict]:
        """Fetch match data from the BSM API and return computed standings."""
        params = {"compact": "true"}
        session = async_get_clientsession(self.hass)
        try:
            url = API_URL_LEAGUE.replace("{league_id}", self.league_id)
            async with session.get(url, params=params, timeout=30) as response:
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

        table, standings, total_home_runs, total_away_runs = _compute_standings(matches)
        if not standings:
            _LOGGER.warning(
                "No standings could be computed for BSM league %s "
                "(no completed matches found)",
                self._league_id,
            )
        self.total_home_runs = total_home_runs
        self.total_away_runs = total_away_runs
        self.team_games = standings[self._team_id]["games"]
        self.last_updated = datetime.now(timezone.utc)
        return table
