"""Constants for the BBSV Teamtracker integration."""

DOMAIN = "bbsv_teamtracker"

CONF_LEAGUE_ID = "league_id"
CONF_TEAM_ID = "team_id"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_NAME = "BBSV Teamtracker"
DEFAULT_SCAN_INTERVAL = 3600  # seconds (1 hour)

# BSM JSON API endpoint for match results
API_URL = "https://bsm.baseball-softball.de/matches.json"
API_URL_LEAGUE = "https://bsm.baseball-softball.de/league_groups/{league_id}/matches.json?compact=true"

# Attribute names exposed on the sensor
ATTR_TABLE = "table"
ATTR_LEAGUE_ID = "league_id"
ATTR_TEAM_ID = "team_id"
ATTR_LAST_UPDATED = "last_updated"
ATTR_HOME_RUNS = "home_runs"
ATTR_AWAY_RUNS = "away_runs"
