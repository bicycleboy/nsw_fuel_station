<!-- .github/copilot-instructions.md - guidance for AI coding agents -->
# Copilot / AI agent instructions for NSW Fuel UI

This file gives concise, repository-specific guidance to help AI coding agents be immediately productive in the nsw_fuel_ui Home Assistant integration.

## Purpose & Overview

**Purpose**: Maintain the NSW Fuel UI Home Assistant integration—a custom component that displays fuel prices from the NSW FuelCheck API using a multi-location, multi-fuel-type model with Home Assistant config flows and sensors.

**Big Picture**:
- Users configure **nicknames** (e.g., "Home", "Work"), each associated with a **location** and a set of **stations** across Australian states
- The **config flow** (`config_flow.py`) guides users through: API credentials → location selection → station selection → optional fuel type filtering
- The **coordinator** (`coordinator.py`) fetches fuel prices for all configured stations via the `nsw_fuel` (nsw-fuel-api-client) library
- **Sensors** (`sensor.py`) render fuel prices—two types: favorite station prices per nickname, cheapest stations per fuel type per nickname
- Data flows: Config entry → Coordinator (update interval: 720 min) → Sensors → Home Assistant UI

## Key Files & Responsibilities

| File | Purpose |
|------|---------|
| `config_flow.py` | Multi-step config flow: credentials → location → station selection; deduplicates stations across config entries |
| `coordinator.py` | Wraps `NSWFuelApiClient`; fetches and caches fuel prices for all stations; raises `ConfigEntryAuthFailed`/`UpdateFailed` on error |
| `sensor.py` | Creates `FuelPriceSensor` and `CheapestFuelSensor` entities; each consumes coordinator data |
| `data.py` | Type aliases: `NSWFuelConfigEntry`, `StationKey` (code, state tuple), `CoordinatorData` (nested dict structure) |
| `const.py` | Constants: domain, fuel types (E10, U91, DL, etc.), state bounds, defaults |
| `__init__.py` | Setup/teardown: instantiates API client and coordinator; manages platform forward |
| `manifest.json` | Metadata: requires `homeassistant>=2025.12.0`, `aiohttp>=3.9` |
| `tests/test_config_flow.py` | Mocks `NSWFuelApiClient`; tests all config flow steps and error paths |

## Critical Patterns & Conventions

### Config Flow Multi-Step Logic
```python
# async_step_user → async_step_location_select → async_step_station_select
# Each step stores state in self._flow_data, re-entered via await self.async_step_*()
# Station deduplication: gather existing_station_codes from all config entries, filter available_stations
# Existing nickname handling: merge new fuel_types into station fuel_types set, call async_update_entry()
```

### Coordinator & Data Structure
- **Update interval**: `DEFAULT_SCAN_INTERVAL = 720 minutes` (price updates are infrequent)
- **Error mapping**: `NSWFuelApiClientAuthError` → `ConfigEntryAuthFailed`; `NSWFuelApiClientError` → `UpdateFailed`
- **Data payload** (CoordinatorData):
  ```python
  {
      "favorites": { StationKey: {fuel_type: Price, ...}, ... },
      "cheapest": { nickname: {fuel_type: [price_info_dicts, ...]} }
  }
  ```

### Sensor Entity Patterns
- **FuelPriceSensor**: one per (station, fuel_type) pair; unique_id = `f"{station_code}_{au_state}_{fuel_type}"`
- **CheapestFuelSensor**: one per (nickname, fuel_type) pair; queries coordinator's `cheapest` data; shows cheapest 3 stations
- **Naming**: `_attr_has_entity_name=True`; name set to fuel type or derived from nickname
- **State updates**: pull from coordinator.data on every refresh; set `_attr_available=True` if data present, else `False`

### Config Entry Merging
When adding a new fuel type to an existing nickname:
1. Check if `(station_code, au_state, fuel_type)` tuple already exists → raise `sensor_exists` error
2. If not, merge fuel type into existing station's fuel_types set
3. Call `hass.config_entries.async_update_entry(updating_entry, data=new_data)` to persist
4. Coordinator auto-refreshes; sensors re-render on coordinator listener trigger

### Test Fixtures & Mocking
- **Mock API**: `mock_api_client` fixture returns `AsyncMock(spec=NSWFuelApiClient)` with `get_fuel_prices_within_radius(lat, lon, fuel_type)` returning list of `StationPrice` objects
- **Mock Integration**: use `pytest.mark.asyncio` and `@patch` for HA config_entries registry access
- **Patterns**: access `result["flow_id"]` to continue flow; check `result["type"]` against `FlowResultType`

## Developer Workflows

### Setup & Installation
```bash
cd /workspaces/ha/nsw_fuel_ui
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
```

### Running Tests
```bash
pytest tests/                                    # All tests
pytest tests/test_config_flow.py -v -k station  # Specific test
pytest tests/ --cov=custom_components/nsw_fuel_ui --cov-report=term-missing  # Coverage
```

### Running in Home Assistant (via config folder)
- Config is symlinked at `/workspaces/ha/config`
- Start HA: `python -m homeassistant -c ./config`
- Integration auto-loads from custom_components (see `/workspaces/ha/config/custom_components/nsw_fuel_ui → symlink to repo`)

### Debugging Coordinator Issues
- Add `_LOGGER.debug()` calls in `coordinator.py` to trace API call flow
- Enable debug logging in HA config: `logger: {custom_components.nsw_fuel_ui: debug}`
- Coordinator refresh triggered on config entry reload or every 720 minutes by default

## Integration Points & Dependencies

### External: nsw-fuel-api-client Library
- **Location**: `/workspaces/ha/nsw-fuel-api-client` (separate repo, as dependency)
- **Key classes**: `NSWFuelApiClient(session, client_id, client_secret)` with methods:
  - `get_fuel_prices_within_radius(lat, lon, fuel_type)` → `list[StationPrice]`
  - Returns DTO with `station.code`, `station.name`, `price.price`, `price.last_updated`
- **Errors**: `NSWFuelApiClientAuthError`, `NSWFuelApiClientError` (base)
- **Token management**: handled internally; `_async_get_token` caches bearer token and expiry

### Internal: Home Assistant Framework
- **Config entries**: stored in HA's registry; accessed via `hass.config_entries`
- **Entity registry**: sensor entities auto-registered; removed on config entry unload
- **Sensors platform**: forward setup via `async_setup_entry` in `sensor.py`
- **Update coordinator**: standard HA pattern; coordinator triggers listeners on successful refresh

## Approach to Changes

### When Fixing Bugs
1. **Reproduce** in config flow tests; add test case to `test_config_flow.py`
2. **Localize**: identify exact step/function (e.g., station deduplication logic)
3. **Fix** in source, update DTO or coordinator logic
4. **Re-test**: ensure config entry creation/update still works; no regression in other steps

### When Adding Features
1. Extend **data flow**: update `CoordinatorData` type in `data.py`; update coordinator `_async_update_data()` to populate new fields
2. Extend **config flow** if user input needed: add new `async_step_*()` or update existing schema
3. **Create sensors** if new UI representation needed: add `_SensorClass` and registration in `sensor.py`
4. **Add tests**: test new flow paths, error handling, edge cases in existing `test_config_flow.py`

### Code Style & Quality
- **Type hints**: required for all function signatures (Python 3.9+)
- **Async-first**: all external I/O (`api.get_fuel_prices_within_radius()`) must be awaited; use `asyncio` primitives
- **Logging**: use `_LOGGER` (defined per module); no print() statements
- **HA conventions**: follow Home Assistant style (see attached AGENTS.md, ha-core/.github/copilot-instructions.md for reference)

## Common Pitfalls

- **Don't hardcode nickname/station data in sensors**: pull from coordinator.data—sensors are ephemeral and may be added/removed
- **Don't re-fetch API on every sensor render**: coordinator caches for 720 minutes; sensors must use that cache
- **Don't skip config entry unique ID**: set `unique_id = f"{DOMAIN}_{slugify(flow_nickname)}"` before `async_create_entry()` to prevent duplicates
- **Don't mix config_entries registry reads**: use `self.hass.config_entries.async_entries(DOMAIN)` to safely read other entries during flow
- **Station codes not globally unique**: always pair code with `au_state` to form `StationKey`; tuples used as dict keys in coordinator data

## Example Prompts for AI Agent

- "Add a new sensor that shows the cheapest 5 stations (currently hard-coded to 3) per fuel type per location"
  → Update `const.py` (new constant), `data.py` (update `CoordinatorData` doc), `sensor.py` (adjust sensor list-building logic)

- "Fix config flow so that when user re-enters location selection after station selection, the form re-seeds with previous location value"
  → Inspect `async_step_location_select()` and `async_step_station_select()`; pass `user_input=self._last_form` to preserve state

- "Reduce coordinator update interval from 720 to 60 minutes for testing"
  → Change `DEFAULT_SCAN_INTERVAL` in `__init__.py`; run tests to confirm sensors update more frequently

---

**If anything is unclear** or if you encounter patterns not documented here, please ask and I will iterate on this guidance.
