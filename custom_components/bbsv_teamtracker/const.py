"""Constants for the BBSV Teamtracker integration."""

DOMAIN = "bbsv_teamtracker"

CONF_LEAGUE_ID = "league_id"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_NAME = "BBSV Teamtracker"
DEFAULT_SCAN_INTERVAL = 3600  # seconds (1 hour)

BASE_URL = "https://www.bbsv.de/spielbetrieb/tabelle/"

# Attribute names exposed on the sensor
ATTR_TABLE = "table"
ATTR_LEAGUE_ID = "league_id"
ATTR_LAST_UPDATED = "last_updated"

# Column header mappings (German -> canonical key)
HEADER_MAP: dict[str, str] = {
    "#": "position",
    "pl.": "position",
    "platz": "position",
    "verein": "team",
    "mannschaft": "team",
    "team": "team",
    "sp": "games",
    "spiele": "games",
    "s": "wins",
    "siege": "wins",
    "u": "draws",
    "unentschieden": "draws",
    "n": "losses",
    "niederlagen": "losses",
    "tore": "runs",
    "diff": "goal_diff",
    "td": "goal_diff",
    "torunterschied": "goal_diff",
    "pkt": "points",
    "pkte": "points",
    "punkte": "points",
}
