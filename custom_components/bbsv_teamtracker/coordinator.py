"""DataUpdateCoordinator for BBSV Teamtracker."""
from __future__ import annotations

import logging
from datetime import timedelta

from bs4 import BeautifulSoup

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_URL,
    CONF_LEAGUE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HEADER_MAP,
)

_LOGGER = logging.getLogger(__name__)


def _parse_table(html: str) -> list[dict]:
    """Parse the league table from the BBSV HTML page.

    Returns a list of dicts, one per team row, with canonical keys:
    position, team, games, wins, draws, losses, goals_for, goals_against,
    goal_diff, points.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find the main league table – prefer a table that contains "tabelle" in
    # its class attribute, otherwise fall back to the first <table>.
    table = None
    for tbl in soup.find_all("table"):
        classes = " ".join(tbl.get("class", [])).lower()
        if "tabelle" in classes or "league" in classes or "standings" in classes:
            table = tbl
            break
    if table is None:
        table = soup.find("table")
    if table is None:
        _LOGGER.warning("No table found on BBSV page")
        return []

    # Detect header row to build a column index map.
    col_map: dict[int, str] = {}
    thead = table.find("thead")
    header_row = None
    skip_first_row = False

    if thead:
        header_row = thead.find("tr")
    else:
        # Only treat the first row as a header when it contains <th> elements.
        first_row = table.find("tr")
        if first_row and first_row.find("th"):
            header_row = first_row
            skip_first_row = True

    if header_row:
        for idx, th in enumerate(header_row.find_all(["th", "td"])):
            raw = th.get_text(strip=True).lower()
            canonical = HEADER_MAP.get(raw)
            if canonical:
                col_map[idx] = canonical

    # If we couldn't detect headers, assume a common column order:
    # 0=position, 1=team, 2=games, 3=wins, 4=draws, 5=losses,
    # 6=goals, 7=goal_diff, 8=points
    if not col_map:
        for idx, key in enumerate(
            ["position", "team", "games", "wins", "draws", "losses",
             "goals", "goal_diff", "points"]
        ):
            col_map[idx] = key

    # Parse data rows.
    tbody = table.find("tbody")
    if tbody:
        rows = tbody.find_all("tr")
    else:
        all_rows = table.find_all("tr")
        rows = all_rows[1:] if skip_first_row else all_rows

    teams: list[dict] = []
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue

        entry: dict = {}
        for idx, value in enumerate(cells):
            key = col_map.get(idx)
            if key is None:
                continue
            if key == "position":
                try:
                    entry["position"] = int(value)
                except ValueError:
                    entry["position"] = None
            elif key == "team":
                entry["team"] = value
            elif key == "goals":
                # Format may be "25:10" or "25-10"
                if ":" in value:
                    parts = value.split(":", 1)
                elif "-" in value:
                    parts = value.split("-", 1)
                else:
                    parts = [value, "0"]
                try:
                    entry["goals_for"] = int(parts[0])
                    entry["goals_against"] = int(parts[1])
                except (ValueError, IndexError):
                    entry["goals_for"] = 0
                    entry["goals_against"] = 0
            elif key == "goal_diff":
                try:
                    entry["goal_diff"] = int(value.replace("+", ""))
                except ValueError:
                    entry["goal_diff"] = None
            else:
                # Numeric field: games, wins, draws, losses, points
                try:
                    entry[key] = int(value)
                except ValueError:
                    entry[key] = None

        # Only add rows that have at minimum a team name.
        if entry.get("team"):
            # Derive goal_diff from goals if not provided by its own column.
            if "goal_diff" not in entry and "goals_for" in entry and "goals_against" in entry:
                goals_for = entry.get("goals_for") or 0
                goals_against = entry.get("goals_against") or 0
                entry["goal_diff"] = goals_for - goals_against
            # Fill missing numeric fields with None to keep schema stable.
            for field in ("position", "games", "wins", "draws", "losses",
                          "goals_for", "goals_against", "goal_diff", "points"):
                entry.setdefault(field, None)
            teams.append(entry)

    return teams


class BBSVTeamtrackerCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches and parses the BBSV league table."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
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
        """Fetch and parse data from the BBSV website."""
        url = f"{BASE_URL}?bsm_league={self._league_id}"
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url, timeout=30) as response:
                response.raise_for_status()
                html = await response.text()
        except Exception as exc:
            raise UpdateFailed(
                f"Error fetching BBSV league table for league {self._league_id}: {exc}"
            ) from exc

        teams = _parse_table(html)
        if not teams:
            _LOGGER.warning(
                "No table data found for BBSV league %s at %s",
                self._league_id,
                url,
            )
        return teams
