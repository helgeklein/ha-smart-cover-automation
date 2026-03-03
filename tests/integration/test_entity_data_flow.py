"""Integration tests for entity data flow with a real Home Assistant instance.

These tests verify that after a coordinator refresh, HA entities expose the
correct state values.  Unlike the ``components/`` tests (which mock the
coordinator), these use a real HA instance so that data type mismatches
between ``CoordinatorData`` / ``CoverState`` and entity ``native_value`` /
``is_on`` are caught.

See developer_docs/test-relevance-improvement-plan.md, Phase 2.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_cover_automation import DOMAIN
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    BINARY_SENSOR_KEY_LOCK_ACTIVE,
    BINARY_SENSOR_KEY_STATUS,
    BINARY_SENSOR_KEY_TEMP_HOT,
    BINARY_SENSOR_KEY_WEATHER_SUNNY,
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    DATA_COORDINATORS,
    NUMBER_KEY_COVERS_MAX_CLOSURE,
    NUMBER_KEY_COVERS_MIN_CLOSURE,
    NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
    NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
    NUMBER_KEY_TEMP_THRESHOLD,
    SELECT_KEY_LOCK_MODE,
    SENSOR_KEY_SUN_AZIMUTH,
    SENSOR_KEY_SUN_ELEVATION,
    SENSOR_KEY_TEMP_CURRENT_MAX,
    LockMode,
)

# ============================================================================
# Constants
# ============================================================================

# --- Test entity IDs ---
TEST_COVER = "cover.dataflow_test_cover"
TEST_WEATHER = "weather.dataflow_test"
ENTRY_ID = "dataflow_test_entry"

# --- Temperature ---
HOT_TEMP = 30.0

# --- Sun geometry ---
SUN_ELEVATION = 45.0
SUN_AZIMUTH = 180.0

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this module."""

    yield


@pytest.fixture(autouse=True)
async def setup_dependencies(hass: HomeAssistant):
    """Set up required dependencies (sun component, logbook mock)."""

    await async_setup_component(hass, "sun", {})
    hass.config.components.add("logbook")
    await hass.async_block_till_done()
    yield


@pytest.fixture(autouse=True)
def expected_lingering_tasks() -> bool:
    """Coordinator timers may linger after test teardown — that's expected."""

    return True


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Coordinator timers may linger after test teardown — that's expected."""

    return True


# ============================================================================
# Helpers
# ============================================================================


#
# _create_config_entry
#
def _create_config_entry(
    hass: HomeAssistant,
    extra_options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Create and register a config entry with sensible defaults.

    Args:
        hass: Home Assistant instance.
        extra_options: Additional or overridden option keys.

    Returns:
        The ``MockConfigEntry`` added to *hass*.
    """

    options: dict[str, Any] = {
        ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
        ConfKeys.COVERS.value: [TEST_COVER],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 10.0,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        ConfKeys.COVERS_MAX_CLOSURE.value: 0,
        ConfKeys.COVERS_MIN_CLOSURE.value: 100,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        ConfKeys.TEMP_THRESHOLD.value: 24.0,
        f"{TEST_COVER}_{COVER_SFX_AZIMUTH}": SUN_AZIMUTH,
    }

    if extra_options:
        options.update(extra_options)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Data Flow Test",
        data={},
        options=options,
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


#
# _setup_integration
#
async def _setup_integration(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    temp_max: float = HOT_TEMP,
) -> None:
    """Load the integration with entity states and patched weather forecast.

    Args:
        hass: Home Assistant instance.
        entry: Config entry (already added to *hass*).
        temp_max: Forecast max temperature in °C.
    """

    covers = entry.options.get(ConfKeys.COVERS.value, [])

    # --- Entity states ---
    hass.states.async_set(
        TEST_WEATHER,
        "sunny",
        {"temperature": 20, "temperature_unit": "°C"},
    )
    hass.states.async_set(
        "sun.sun",
        "above_horizon",
        {"elevation": SUN_ELEVATION, "azimuth": SUN_AZIMUTH},
    )
    for cover_id in covers:
        state = "open"
        hass.states.async_set(
            cover_id,
            state,
            {
                "current_position": COVER_POS_FULLY_OPEN,
                "supported_features": 15,  # OPEN | CLOSE | SET_POSITION | STOP
            },
        )

    # Register mock cover service
    if not hass.services.has_service("cover", "set_cover_position"):

        async def _noop(call) -> None:  # noqa: ARG001
            """No-op handler."""

        hass.services.async_register("cover", "set_cover_position", _noop)

    # Patch the forecast retrieval
    with patch(
        "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface._get_forecast_max_temp",
        new_callable=AsyncMock,
        return_value=temp_max,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED


#
# _get_coordinator
#
def _get_coordinator(hass: HomeAssistant, entry: MockConfigEntry):  # noqa: ANN202
    """Retrieve the coordinator for a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry to look up.

    Returns:
        The ``DataUpdateCoordinator`` instance.
    """

    return hass.data[DOMAIN][DATA_COORDINATORS][entry.entry_id]


#
# _entity_id_for_key
#
def _entity_id_for_key(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    key: str,
) -> str | None:
    """Look up the entity_id registered for a given entity key.

    Uses the entity registry to find the entity by its unique_id
    (``{entry_id}_{key}``), which avoids hard-coding translated names.

    Args:
        hass: Home Assistant instance.
        entry: Config entry whose entities to search.
        key: Entity description key (e.g. ``"status"``, ``"sun_azimuth"``).

    Returns:
        The entity_id string, or ``None`` if not found.
    """

    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_{key}"
    reg_entry = registry.async_get_entity_id(None, DOMAIN, unique_id)

    # async_get_entity_id returns entity_id or None, but when we don't know
    # the platform we iterate manually.
    if reg_entry is not None:
        return reg_entry

    # Fallback: iterate all entries for this config entry
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id == unique_id:
            return entity.entity_id

    return None


# ============================================================================
# Tests — Phase 2: Entity Data Flow
# ============================================================================


class TestBinarySensorDataFlow:
    """Verify binary sensor entities reflect coordinator data correctly."""

    # ------------------------------------------------------------------
    # 2.1  Status binary sensor reflects coordinator health
    # ------------------------------------------------------------------

    #
    # test_status_sensor_reflects_coordinator_health
    #
    async def test_status_sensor_reflects_coordinator_health(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Status binary sensor is OFF when coordinator succeeds (no problem).

        ``StatusBinarySensor.is_on`` returns
        ``not coordinator.last_update_success``, so a healthy coordinator
        should have the status sensor *off* (no problem detected).
        """

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, BINARY_SENSOR_KEY_STATUS)
        assert entity_id is not None, "Status binary sensor not registered"

        state = hass.states.get(entity_id)
        assert state is not None, f"No state for {entity_id}"
        # Coordinator succeeded → no problem → OFF
        assert state.state == "off", f"Status sensor should be 'off' (no problem) but is '{state.state}'"

    # ------------------------------------------------------------------
    # 2.2  temp_hot binary sensor matches coordinator data
    # ------------------------------------------------------------------

    #
    # test_temp_hot_sensor_reflects_coordinator_data
    #
    async def test_temp_hot_sensor_reflects_coordinator_data(
        self,
        hass: HomeAssistant,
    ) -> None:
        """temp_hot binary sensor is ON when forecast exceeds threshold.

        Default threshold is 24 °C.  With ``HOT_TEMP = 30``, the sensor
        should report ON.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry, temp_max=HOT_TEMP)

        entity_id = _entity_id_for_key(hass, entry, BINARY_SENSOR_KEY_TEMP_HOT)
        assert entity_id is not None, "temp_hot binary sensor not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on", f"temp_hot should be 'on' with {HOT_TEMP}°C > threshold, got '{state.state}'"

    # ------------------------------------------------------------------
    # 2.3  weather_sunny binary sensor
    # ------------------------------------------------------------------

    #
    # test_weather_sunny_sensor_reflects_coordinator_data
    #
    async def test_weather_sunny_sensor_reflects_coordinator_data(
        self,
        hass: HomeAssistant,
    ) -> None:
        """weather_sunny binary sensor is ON when weather condition is sunny."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, BINARY_SENSOR_KEY_WEATHER_SUNNY)
        assert entity_id is not None, "weather_sunny binary sensor not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on", f"weather_sunny should be 'on' with sunny weather, got '{state.state}'"

    # ------------------------------------------------------------------
    # 2.4  lock_active binary sensor (unlocked → ON)
    # ------------------------------------------------------------------

    #
    # test_lock_active_sensor_unlocked
    #
    async def test_lock_active_sensor_unlocked(
        self,
        hass: HomeAssistant,
    ) -> None:
        """lock_active binary sensor is ON when lock mode is UNLOCKED.

        The sensor uses device_class LOCK, so ON = unlocked.
        ``is_on = not coordinator.is_locked``.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, BINARY_SENSOR_KEY_LOCK_ACTIVE)
        assert entity_id is not None, "lock_active binary sensor not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        # Default lock mode is UNLOCKED → is_locked=False → is_on=True → "on"
        assert state.state == "on", f"lock_active should be 'on' (unlocked), got '{state.state}'"

    # ------------------------------------------------------------------
    # 2.5  lock_active binary sensor (locked → OFF)
    # ------------------------------------------------------------------

    #
    # test_lock_active_sensor_locked
    #
    async def test_lock_active_sensor_locked(
        self,
        hass: HomeAssistant,
    ) -> None:
        """lock_active binary sensor is OFF when lock mode is FORCE_CLOSE."""

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.LOCK_MODE.value: LockMode.FORCE_CLOSE},
        )
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, BINARY_SENSOR_KEY_LOCK_ACTIVE)
        assert entity_id is not None

        state = hass.states.get(entity_id)
        assert state is not None
        # FORCE_CLOSE → is_locked=True → is_on=False → "off"
        assert state.state == "off", f"lock_active should be 'off' (locked), got '{state.state}'"


class TestSensorDataFlow:
    """Verify sensor entities expose correct coordinator data."""

    # ------------------------------------------------------------------
    # 2.6  Sun azimuth sensor
    # ------------------------------------------------------------------

    #
    # test_sun_azimuth_sensor_value
    #
    async def test_sun_azimuth_sensor_value(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Sun azimuth sensor shows coordinator's sun_azimuth value."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, SENSOR_KEY_SUN_AZIMUTH)
        assert entity_id is not None, "sun_azimuth sensor not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == SUN_AZIMUTH

    # ------------------------------------------------------------------
    # 2.7  Sun elevation sensor
    # ------------------------------------------------------------------

    #
    # test_sun_elevation_sensor_value
    #
    async def test_sun_elevation_sensor_value(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Sun elevation sensor shows coordinator's sun_elevation value."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, SENSOR_KEY_SUN_ELEVATION)
        assert entity_id is not None, "sun_elevation sensor not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == SUN_ELEVATION

    # ------------------------------------------------------------------
    # 2.8  Current max temperature sensor
    # ------------------------------------------------------------------

    #
    # test_temp_current_max_sensor_value
    #
    async def test_temp_current_max_sensor_value(
        self,
        hass: HomeAssistant,
    ) -> None:
        """temp_current_max sensor shows the forecast max temperature."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry, temp_max=HOT_TEMP)

        entity_id = _entity_id_for_key(hass, entry, SENSOR_KEY_TEMP_CURRENT_MAX)
        assert entity_id is not None, "temp_current_max sensor not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert float(state.state) == HOT_TEMP


class TestNumberEntityDataFlow:
    """Verify number entities read from config and persist changes."""

    # ------------------------------------------------------------------
    # 2.9  Number entity reads default config value
    # ------------------------------------------------------------------

    #
    # test_number_entity_reads_default_value
    #
    async def test_number_entity_reads_default_value(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Number entity native_value reflects the config default."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, NUMBER_KEY_TEMP_THRESHOLD)
        assert entity_id is not None, "temp_threshold number entity not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        # Default is 24.0
        assert float(state.state) == 24.0

    # ------------------------------------------------------------------
    # 2.10  Number entity persists new value to config options
    # ------------------------------------------------------------------

    #
    # test_number_entity_persists_new_value
    #
    async def test_number_entity_persists_new_value(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Setting a number entity value persists to config entry options.

        Calls ``number.set_value`` service on the temp_threshold entity and
        verifies the new value appears in ``entry.options``.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, NUMBER_KEY_TEMP_THRESHOLD)
        assert entity_id is not None

        new_value = 28.0
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": new_value},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Verify persisted in config options
        assert entry.options.get(ConfKeys.TEMP_THRESHOLD.value) == new_value

    # ------------------------------------------------------------------
    # 2.11  Multiple number entities reflect their respective config keys
    # ------------------------------------------------------------------

    #
    # test_multiple_number_entities_reflect_config
    #
    async def test_multiple_number_entities_reflect_config(
        self,
        hass: HomeAssistant,
    ) -> None:
        """All number entities reflect their corresponding config values."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        # Map of entity key → expected default value
        expected_values = {
            NUMBER_KEY_TEMP_THRESHOLD: 24.0,
            NUMBER_KEY_SUN_ELEVATION_THRESHOLD: 10.0,
            NUMBER_KEY_SUN_AZIMUTH_TOLERANCE: 90.0,
            NUMBER_KEY_COVERS_MAX_CLOSURE: 0.0,
            NUMBER_KEY_COVERS_MIN_CLOSURE: 100.0,
        }

        for key, expected in expected_values.items():
            entity_id = _entity_id_for_key(hass, entry, key)
            assert entity_id is not None, f"Number entity {key} not registered"

            state = hass.states.get(entity_id)
            assert state is not None, f"No state for {entity_id}"
            assert float(state.state) == expected, f"{key}: expected {expected}, got {state.state}"


class TestSelectEntityDataFlow:
    """Verify select entity reads and writes lock mode correctly."""

    # ------------------------------------------------------------------
    # 2.12  Select entity reads default lock mode
    # ------------------------------------------------------------------

    #
    # test_select_reads_default_lock_mode
    #
    async def test_select_reads_default_lock_mode(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Lock mode select shows UNLOCKED by default."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, SELECT_KEY_LOCK_MODE)
        assert entity_id is not None, "lock_mode select entity not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == LockMode.UNLOCKED

    # ------------------------------------------------------------------
    # 2.13  Selecting a lock mode updates coordinator and config
    # ------------------------------------------------------------------

    #
    # test_select_changes_lock_mode
    #
    async def test_select_changes_lock_mode(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Changing lock mode via select entity updates config options."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, SELECT_KEY_LOCK_MODE)
        assert entity_id is not None

        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": LockMode.FORCE_OPEN},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Coordinator should reflect new lock mode
        coordinator = _get_coordinator(hass, entry)
        assert coordinator.lock_mode == LockMode.FORCE_OPEN

        # Config options should be persisted
        assert entry.options.get(ConfKeys.LOCK_MODE.value) == LockMode.FORCE_OPEN


class TestSwitchEntityDataFlow:
    """Verify switch entities toggle config and reflect state."""

    # ------------------------------------------------------------------
    # 2.14  Enabled switch reads default (True)
    # ------------------------------------------------------------------

    #
    # test_enabled_switch_default_on
    #
    async def test_enabled_switch_default_on(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Enabled switch is ON by default."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, ConfKeys.ENABLED.value)
        assert entity_id is not None, "enabled switch not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"

    # ------------------------------------------------------------------
    # 2.15  Toggling enabled switch persists to config
    # ------------------------------------------------------------------

    #
    # test_enabled_switch_turn_off_persists
    #
    async def test_enabled_switch_turn_off_persists(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Turning off the enabled switch persists False to config options."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, ConfKeys.ENABLED.value)
        assert entity_id is not None

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert entry.options.get(ConfKeys.ENABLED.value) is False

    # ------------------------------------------------------------------
    # 2.16  Simulation mode switch reads default (False)
    # ------------------------------------------------------------------

    #
    # test_simulation_mode_switch_default_off
    #
    async def test_simulation_mode_switch_default_off(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Simulation mode switch is OFF by default."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, ConfKeys.SIMULATION_MODE.value)
        assert entity_id is not None, "simulation_mode switch not registered"

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "off"

    # ------------------------------------------------------------------
    # 2.17  Toggling simulation mode switch persists to config
    # ------------------------------------------------------------------

    #
    # test_simulation_mode_switch_turn_on_persists
    #
    async def test_simulation_mode_switch_turn_on_persists(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Turning on simulation mode persists True to config options."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        entity_id = _entity_id_for_key(hass, entry, ConfKeys.SIMULATION_MODE.value)
        assert entity_id is not None

        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert entry.options.get(ConfKeys.SIMULATION_MODE.value) is True


class TestEntityRegistration:
    """Verify entity registration and unique_id wiring."""

    # ------------------------------------------------------------------
    # 2.18  All expected entities are registered
    # ------------------------------------------------------------------

    #
    # test_all_expected_entities_registered
    #
    async def test_all_expected_entities_registered(
        self,
        hass: HomeAssistant,
    ) -> None:
        """All expected platform entities are created in the entity registry.

        Checks that every known entity key has a corresponding registry entry,
        catching typos or missing ``async_add_entities`` calls.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)

        registered_keys = {e.unique_id.removeprefix(f"{ENTRY_ID}_") for e in entities}

        # Binary sensors
        for key in (
            BINARY_SENSOR_KEY_STATUS,
            BINARY_SENSOR_KEY_TEMP_HOT,
            BINARY_SENSOR_KEY_WEATHER_SUNNY,
            BINARY_SENSOR_KEY_LOCK_ACTIVE,
        ):
            assert key in registered_keys, f"Binary sensor '{key}' not registered"

        # Sensors
        for key in (
            SENSOR_KEY_SUN_AZIMUTH,
            SENSOR_KEY_SUN_ELEVATION,
            SENSOR_KEY_TEMP_CURRENT_MAX,
        ):
            assert key in registered_keys, f"Sensor '{key}' not registered"

        # Number entities
        for key in (
            NUMBER_KEY_TEMP_THRESHOLD,
            NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
            NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
            NUMBER_KEY_COVERS_MAX_CLOSURE,
            NUMBER_KEY_COVERS_MIN_CLOSURE,
        ):
            assert key in registered_keys, f"Number entity '{key}' not registered"

        # Select
        assert SELECT_KEY_LOCK_MODE in registered_keys, "Lock mode select not registered"

        # Switches
        for key in (
            ConfKeys.ENABLED.value,
            ConfKeys.SIMULATION_MODE.value,
        ):
            assert key in registered_keys, f"Switch '{key}' not registered"

    # ------------------------------------------------------------------
    # 2.19  All entities belong to integration platform
    # ------------------------------------------------------------------

    #
    # test_all_entities_belong_to_integration
    #
    async def test_all_entities_belong_to_integration(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Every registered entity has platform == DOMAIN."""

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry)

        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)

        assert len(entities) > 0, "No entities registered"
        for entity in entities:
            assert entity.platform == DOMAIN, f"Entity {entity.entity_id} has platform '{entity.platform}', expected '{DOMAIN}'"
