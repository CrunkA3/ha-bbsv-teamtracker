"""Sensor platform for BBSV Teamtracker."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_LAST_UPDATED,
    ATTR_LEAGUE_ID,
    ATTR_TABLE,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import BBSVTeamtrackerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BBSV Teamtracker sensor from a config entry."""
    coordinator: BBSVTeamtrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BBSVLeagueTableSensor(coordinator, entry)])


class BBSVLeagueTableSensor(CoordinatorEntity[BBSVTeamtrackerCoordinator], SensorEntity):
    """Sensor that exposes the full BBSV league table."""

    _attr_icon = "mdi:trophy-variant"
    _attr_native_unit_of_measurement = "teams"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BBSVTeamtrackerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        league_id = coordinator.league_id
        self._attr_unique_id = f"{DOMAIN}_{league_id}_table"
        user_name: str = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_name = user_name

    @property
    def native_value(self) -> int | None:
        """Return the number of teams in the table."""
        if self.coordinator.data is None:
            return None
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the full league table and metadata."""
        attrs: dict = {
            ATTR_LEAGUE_ID: self.coordinator.league_id,
            ATTR_TABLE: self.coordinator.data or [],
        }
        if self.coordinator.last_update_success and self.coordinator.last_updated:
            attrs[ATTR_LAST_UPDATED] = self.coordinator.last_updated.isoformat()
        return attrs
