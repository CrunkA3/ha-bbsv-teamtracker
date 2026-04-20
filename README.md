# BBSV Teamtracker

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A [Home Assistant](https://www.home-assistant.io/) custom integration that fetches and exposes the **league table** from the Bayerischer Basketball-Verband (BBSV) website.

## Features

- Fetches the league table from `https://www.bbsv.de/spielbetrieb/tabelle/?bsm_league=<ID>`
- Exposes one sensor per configured league:
  - **State**: number of teams in the table
  - **Attributes**: full table as a list, configurable update interval, last-updated timestamp
- Configurable via the Home Assistant UI (no YAML required)
- Supports multiple leagues simultaneously
- German and English UI translations

## Installation

### HACS (recommended)

1. Open **HACS** → **Integrations** → ⋮ menu → **Custom repositories**
2. Add `https://github.com/CrunkA3/ha-bbsv-teamtracker` with category **Integration**
3. Search for **BBSV Teamtracker** and install it
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/bbsv_teamtracker/` directory into your `<config>/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **BBSV Teamtracker**
3. Enter your **League ID** (the `bsm_league` parameter from the BBSV URL, e.g. `12345`)
4. Optionally give the sensor a custom name
5. Click **Submit**

### Finding your League ID

Navigate to the league table on the BBSV website and look at the URL:

```
https://www.bbsv.de/spielbetrieb/tabelle/?bsm_league=<YOUR_LEAGUE_ID>
```

Copy the numeric value after `bsm_league=`.

## Sensor Attributes

| Attribute | Description |
|---|---|
| `league_id` | The configured BBSV league ID |
| `table` | List of team entries (see below) |
| `last_updated` | ISO 8601 timestamp of the last successful fetch |

### Table entry fields

| Field | Description |
|---|---|
| `position` | Rank in the table |
| `team` | Team / club name |
| `games` | Matches played |
| `wins` | Wins |
| `draws` | Draws |
| `losses` | Losses |
| `goals_for` | Goals scored |
| `goals_against` | Goals conceded |
| `goal_diff` | Goal difference |
| `points` | Points |

## Options

After the integration is set up you can adjust the **update interval** (minimum 60 seconds, default 3600 s / 1 h) via the integration's options dialog.

## Example template sensor (leader)

```yaml
template:
  - sensor:
      - name: "BBSV Table Leader"
        state: >
          {% set table = state_attr('sensor.bbsv_teamtracker', 'table') %}
          {% if table %}{{ table[0]['team'] }}{% else %}unknown{% endif %}
```

## License

MIT – see [LICENSE](LICENSE)
