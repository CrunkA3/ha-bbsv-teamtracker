# Copilot Instructions – BBSV Teamtracker (HACS Custom Integration)

## Project Overview

`ha-bbsv-teamtracker` is a [Home Assistant](https://www.home-assistant.io/) custom integration distributed through [HACS](https://hacs.xyz/).  
It polls the [BSM API](https://bsm.baseball-softball.de) to fetch match results and computes live league standings for any Bayerischer Baseball/Softball-Verband (BBSV) league.

Custom component directory: `custom_components/bbsv_teamtracker/`

---

## Architecture

The integration follows the standard HA custom-integration pattern:

| File | Role |
|---|---|
| `__init__.py` | Entry-point: sets up/tears down a config entry, forwards to platforms, registers the options listener |
| `manifest.json` | HACS / HA integration metadata (domain, version, codeowners, iot_class, …) |
| `const.py` | All shared constants (domain, config keys, attribute names, API URLs) |
| `coordinator.py` | `DataUpdateCoordinator` subclass – fetches data from BSM API, computes standings |
| `config_flow.py` | `ConfigFlow` + `OptionsFlow` – two-step UI: pick league → pick team |
| `sensor.py` | All `SensorEntity` subclasses, each wrapping the coordinator |
| `strings.json` | Master UI strings (English); mirrored in `translations/en.json` and `translations/de.json` |
| `hacs.json` | HACS repository metadata |

### Data flow

```
BSM API (matches.json)
    └─► BBSVTeamtrackerCoordinator._async_update_data()
            └─► _compute_standings()  →  table, standings dict, run totals
                    └─► sensors read coordinator.data / coordinator.*
```

---

## Key Conventions

### Home Assistant patterns to follow

- **Always** use `DataUpdateCoordinator` for periodic data fetching – never poll inside a sensor.
- Sensors **must** inherit from both `CoordinatorEntity[BBSVTeamtrackerCoordinator]` and `SensorEntity`.
- Set `_attr_has_entity_name = True` on every sensor so HA prefixes the entity name with the device name automatically.
- Assign `_attr_unique_id` in `__init__` using the pattern `f"{DOMAIN}_{league_id}_{qualifier}"` to ensure uniqueness across multiple instances.
- Return a shared `DeviceInfo` object (see `_device_info()` in `sensor.py`) for every sensor so they are grouped under one device.
- Use `async_get_clientsession(hass)` for all HTTP requests – never create a raw `aiohttp.ClientSession`.
- Raise `UpdateFailed` (not a bare exception) inside `_async_update_data()` to signal transient errors to the coordinator.
- Use `entry.options.get(..., entry.data.get(..., DEFAULT))` pattern to read config values so that options always override initial data.

### HACS requirements

- `manifest.json` **must** contain: `domain`, `name`, `version`, `config_flow: true`, `documentation`, `issue_tracker`, `requirements`, `codeowners`, `iot_class`.
- `hacs.json` **must** be present at the repository root with at least `"name"`.
- Translation files live under `custom_components/bbsv_teamtracker/translations/<lang>.json`.  
  `strings.json` is the authoritative source; keep `translations/en.json` and `translations/de.json` in sync with it.
- Every new user-visible string must be added to `strings.json` **and** all translation files.

### Adding a new sensor

1. Define a new class in `sensor.py` inheriting from `CoordinatorEntity[BBSVTeamtrackerCoordinator]` and `SensorEntity`.
2. Set `_attr_unique_id`, `_attr_name`, `_attr_icon`, `_attr_has_entity_name = True`, and `_attr_device_info` in `__init__`.
3. Implement `native_value` and `extra_state_attributes` as `@property`.
4. Instantiate the sensor in `async_setup_entry()` and append it to `sensors`.
5. If the sensor requires data computed during the update cycle, add the attribute to `BBSVTeamtrackerCoordinator` (initialised in `__init__`, populated in `_async_update_data`).

### Adding a new config/options field

1. Add the constant to `const.py` (e.g. `CONF_FOO = "foo"`).
2. Add the `vol.Schema` field in `config_flow.py` (both `ConfigFlow` step and `OptionsFlow.async_step_init` if applicable).
3. Add the UI label to `strings.json` → `config.step.<step>.data.<key>` and mirror it in all translation files.
4. Read the value in the coordinator or sensor using `entry.options.get(CONF_FOO, entry.data.get(CONF_FOO, DEFAULT))`.

---

## API Reference

| Endpoint | Usage |
|---|---|
| `https://bsm.baseball-softball.de/matches.json?compact=true` | All matches (used in config flow to build league list) |
| `https://bsm.baseball-softball.de/league_groups/{league_id}/matches.json?compact=true` | Matches filtered by league (used in config flow for team list)  (used by the coordinator) |

Match records include: `home_team_name`, `away_team_name`, `home_runs`, `away_runs`, `league.id`, `league.name`.  
A match is **completed** when both `home_runs` and `away_runs` are numeric values.

---

## Standings Computation (`_compute_standings`)

- Iterates all completed matches.
- Tracks per-team: `games`, `wins`, `losses`, `runs_for`, `runs_against`.
- Win = more runs scored; tied games count as a game played but award neither win nor loss nor points.
- Points = `wins × 2`.
- Sort order: points desc → run_diff desc → runs_for desc → team name asc.

---

## Code Style

- Python 3.12+, `from __future__ import annotations` at the top of every module.
- All async functions; no blocking I/O in the event loop.
- Type annotations on all function signatures.
- Docstrings on every class and public method (one-liner for trivial properties).
- `noqa: BLE001` is acceptable on broad `except Exception` blocks when the exception is logged immediately after.
- Do **not** use `YAML` configuration – this integration is UI-only (`config_flow: true`).
