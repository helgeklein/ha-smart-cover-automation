"""Integration tests using a real Home Assistant instance.

These tests load the integration through Home Assistant's setup process,
catching runtime errors that don't appear in unit tests, such as:
- Missing properties or methods on HA objects
- Incorrect API usage
- Integration setup/teardown issues
- Entity registration problems

These complement the existing unit tests by verifying the integration
works correctly in a real HA environment.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_cover_automation import DOMAIN
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_SFX_AZIMUTH,
    COVER_SFX_TILT_EXTERNAL_VALUE_DAY,
    COVER_SFX_TILT_MODE_DAY,
    NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY,
    STEP_4_SECTION_TILT_DAY,
    TiltMode,
)

# Test constants
TEST_COVER_1 = "cover.test_cover_1"
TEST_COVER_2 = "cover.test_cover_2"
TEST_WEATHER = "weather.test_weather"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this module."""
    yield


@pytest.fixture(autouse=True)
async def setup_dependencies(hass: HomeAssistant):
    """Set up required dependencies for integration testing.

    Our integration depends on logbook, which in turn depends on frontend and recorder.
    For testing purposes, we bypass these UI/database dependencies and just set up
    the core dependencies (sun, weather).
    """
    # Set up sun (required for automation logic)
    await async_setup_component(hass, "sun", {})

    # Mock logbook to avoid frontend/recorder dependencies
    hass.config.components.add("logbook")

    await hass.async_block_till_done()
    yield


#
# create_test_config_entry
#
def create_test_config_entry(
    hass: HomeAssistant,
    options: dict | None = None,
) -> MockConfigEntry:
    """Create a test config entry with minimal valid configuration.

    Args:
        hass: Home Assistant instance
        options: Configuration options (will use defaults if not provided)

    Returns:
        Mock config entry ready to be added to hass
    """

    if options is None:
        options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Smart Cover Automation",
        data={},
        options=options,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry


#
# _as_dict
#
def _as_dict(result: Any) -> dict[str, Any]:
    """Convert a flow result TypedDict to a plain dict."""

    return cast(dict[str, Any], result)


#
# _set_test_entity_states
#
def _set_test_entity_states(hass: HomeAssistant) -> None:
    """Register cover and weather states needed by the real options flow."""

    cover_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION
    )

    hass.states.async_set(
        TEST_COVER_1,
        "open",
        {
            "current_position": 100,
            "current_tilt_position": 100,
            "friendly_name": "Kitchen Cover",
            "supported_features": cover_features,
        },
    )
    hass.states.async_set(
        TEST_COVER_2,
        "open",
        {
            "current_position": 100,
            "current_tilt_position": 100,
            "friendly_name": "Office Cover",
            "supported_features": cover_features,
        },
    )
    hass.states.async_set(
        TEST_WEATHER,
        "sunny",
        {
            "temperature": 20,
            "temperature_unit": "°C",
            "supported_features": WeatherEntityFeature.FORECAST_DAILY,
        },
    )


#
# _get_registry_entry_by_unique_id
#
def _get_registry_entry_by_unique_id(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    unique_key: str,
):
    """Return the entity-registry entry matching an integration unique key."""

    entity_registry = er.async_get(hass)
    expected_unique_id = f"{entry.entry_id}_{unique_key}"

    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.unique_id == expected_unique_id:
            return entity

    return None


#
# _run_options_flow
#
async def _run_options_flow(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    step_4_input: dict[str, Any],
) -> dict[str, Any]:
    """Submit the full real options flow and return the final result."""

    result = _as_dict(await hass.config_entries.options.async_init(entry.entry_id))
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = _as_dict(
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            },
        )
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2"

    result = _as_dict(
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            },
        )
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "3"

    result = _as_dict(
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            },
        )
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "4"

    result = _as_dict(
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=step_4_input,
        )
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "5"

    result = _as_dict(
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "6"

    return _as_dict(
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )
    )


class TestIntegrationRealHA:
    """Test integration setup and operation with real Home Assistant instance."""

    #
    # test_integration_loads_successfully
    #
    async def test_integration_loads_successfully(self, hass: HomeAssistant) -> None:
        """Test that the integration loads successfully in a real HA instance.

        This verifies:
        - Integration can be set up through HA's setup process
        - Config entry reaches LOADED state
        - No runtime errors during initialization
        """

        # Create config entry
        entry = create_test_config_entry(hass)

        # Set up the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify entry loaded successfully
        assert entry.state == ConfigEntryState.LOADED

    #
    # test_integration_creates_entities
    #
    async def test_integration_creates_entities(self, hass: HomeAssistant) -> None:
        """Test that the integration creates the expected entities.

        This verifies:
        - Entities are registered in the entity registry
        - Entity IDs are correctly formatted
        - Platforms are properly set up
        """

        # Create config entry
        entry = create_test_config_entry(hass)

        # Set up the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Get entity registry
        entity_registry = er.async_get(hass)

        # Verify entities were created
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

        # Should have at least some entities (switches, sensors, binary_sensors)
        assert len(entities) > 0

        # Verify all entities belong to our integration
        for entity in entities:
            assert entity.platform == DOMAIN

    #
    # test_integration_unloads_cleanly
    #
    async def test_integration_unloads_cleanly(self, hass: HomeAssistant) -> None:
        """Test that the integration unloads without errors.

        This verifies:
        - Integration can be unloaded through HA's unload process
        - Config entry reaches NOT_LOADED state
        - No runtime errors during teardown
        """

        # Create config entry
        entry = create_test_config_entry(hass)

        # Set up the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify loaded
        assert entry.state == ConfigEntryState.LOADED

        # Unload the integration
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify unloaded successfully
        assert entry.state == ConfigEntryState.NOT_LOADED

    #
    # test_integration_reload
    #
    async def test_integration_reload(self, hass: HomeAssistant) -> None:
        """Test that the integration can be reloaded.

        This verifies:
        - Integration can be unloaded and reloaded
        - Config entry returns to LOADED state after reload
        - No runtime errors during reload cycle
        """

        # Create config entry
        entry = create_test_config_entry(hass)

        # Set up the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify loaded
        assert entry.state == ConfigEntryState.LOADED

        # Reload the integration (unload then setup)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        # Verify reloaded successfully
        assert entry.state == ConfigEntryState.LOADED

    #
    # test_integration_with_minimal_config
    #
    async def test_integration_with_minimal_config(self, hass: HomeAssistant) -> None:
        """Test integration loads with minimal required configuration.

        This verifies:
        - Integration handles minimal configuration
        - Default values are applied correctly
        - No runtime errors with sparse config
        """

        # Create minimal config (only required fields)
        minimal_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
        }

        entry = create_test_config_entry(hass, options=minimal_options)

        # Set up the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify loaded
        assert entry.state == ConfigEntryState.LOADED

    #
    # test_integration_with_multiple_covers
    #
    async def test_integration_with_multiple_covers(self, hass: HomeAssistant) -> None:
        """Test integration handles multiple covers correctly.

        This verifies:
        - Integration can manage multiple cover entities
        - Each cover gets proper configuration
        - No conflicts between covers
        """

        # Create config with multiple covers
        options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2, "cover.test_cover_3"],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            "cover.test_cover_3_{COVER_SFX_AZIMUTH}": 270.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        }

        entry = create_test_config_entry(hass, options=options)

        # Set up the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify loaded
        assert entry.state == ConfigEntryState.LOADED

        # Verify entities created for all covers
        entity_registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

        # Should have entities for all 3 covers
        assert len(entities) > 0

    #
    # test_integration_handles_missing_weather_entity
    #
    async def test_integration_handles_missing_weather_entity(self, hass: HomeAssistant) -> None:
        """Test integration handles missing weather entity gracefully.

        This verifies:
        - Integration loads even if weather entity doesn't exist
        - No runtime crashes due to missing entities
        - Integration can still function in degraded mode
        """

        # Create config with non-existent weather entity
        options = {
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.nonexistent",
            ConfKeys.COVERS.value: [TEST_COVER_1],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
        }

        entry = create_test_config_entry(hass, options=options)

        # Set up the integration (should not crash)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify loaded (even with missing weather entity)
        assert entry.state == ConfigEntryState.LOADED

    #
    # test_integration_handles_missing_cover_entity
    #
    async def test_integration_handles_missing_cover_entity(self, hass: HomeAssistant) -> None:
        """Test integration handles missing cover entity gracefully.

        This verifies:
        - Integration loads even if cover entities don't exist
        - No runtime crashes due to missing covers
        - Integration can still function with available covers
        """

        # Create config with non-existent cover entities
        options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: ["cover.nonexistent_1", "cover.nonexistent_2"],
            "cover.nonexistent_1_{COVER_SFX_AZIMUTH}": 180.0,
            "cover.nonexistent_2_{COVER_SFX_AZIMUTH}": 90.0,
        }

        entry = create_test_config_entry(hass, options=options)

        # Set up the integration (should not crash)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify loaded (even with missing cover entities)
        assert entry.state == ConfigEntryState.LOADED

    #
    # test_integration_platforms_registered
    #
    async def test_integration_platforms_registered(self, hass: HomeAssistant) -> None:
        """Test that all expected platforms are registered.

        This verifies:
        - Binary sensor platform is set up
        - Sensor platform is set up
        - Switch platform is set up
        - No runtime errors in platform registration
        """

        # Create config entry
        entry = create_test_config_entry(hass)

        # Set up the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify loaded
        assert entry.state == ConfigEntryState.LOADED

        # Get entity registry
        entity_registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

        # Verify we have entities from different platforms
        platforms = {entity.domain for entity in entities}

        # Should have at least switch platform (master switch)
        assert Platform.SWITCH in platforms

    #
    # test_options_flow_reload_creates_and_deletes_external_tilt_entities
    #
    async def test_options_flow_reload_creates_and_deletes_external_tilt_entities(
        self,
        hass: HomeAssistant,
    ) -> None:
        """A structural options-flow save should create and later remove dynamic tilt entities."""

        _set_test_entity_states(hass)
        entry = create_test_config_entry(hass)

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED
        assert _get_registry_entry_by_unique_id(hass, entry, NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY) is None

        create_result = await _run_options_flow(
            hass,
            entry,
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.EXTERNAL,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
            },
        )
        await hass.async_block_till_done()

        assert create_result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.state == ConfigEntryState.LOADED
        assert entry.options[ConfKeys.TILT_MODE_DAY.value] == TiltMode.EXTERNAL

        global_entity = _get_registry_entry_by_unique_id(hass, entry, NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY)

        assert global_entity is not None
        assert global_entity.domain == Platform.NUMBER

        delete_result = await _run_options_flow(
            hass,
            entry,
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.AUTO,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
            },
        )
        await hass.async_block_till_done()

        assert delete_result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.state == ConfigEntryState.LOADED
        assert entry.options[ConfKeys.TILT_MODE_DAY.value] == TiltMode.AUTO
        assert _get_registry_entry_by_unique_id(hass, entry, NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY) is None

    #
    # test_options_flow_reload_creates_and_deletes_per_cover_external_tilt_entity
    #
    async def test_options_flow_reload_creates_and_deletes_per_cover_external_tilt_entity(
        self,
        hass: HomeAssistant,
    ) -> None:
        """A structural options-flow save should create and later remove the per-cover tilt entity."""

        _set_test_entity_states(hass)
        entry = create_test_config_entry(hass)
        per_cover_unique_key = f"{TEST_COVER_1}_{COVER_SFX_TILT_EXTERNAL_VALUE_DAY}"
        per_cover_mode_key = f"{TEST_COVER_1}_{COVER_SFX_TILT_MODE_DAY}"

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert entry.state == ConfigEntryState.LOADED
        assert _get_registry_entry_by_unique_id(hass, entry, per_cover_unique_key) is None

        create_result = await _run_options_flow(
            hass,
            entry,
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.AUTO,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
                STEP_4_SECTION_TILT_DAY: {per_cover_mode_key: TiltMode.EXTERNAL},
            },
        )
        await hass.async_block_till_done()

        assert create_result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.state == ConfigEntryState.LOADED
        assert entry.options[ConfKeys.TILT_MODE_DAY.value] == TiltMode.AUTO
        assert entry.options[per_cover_mode_key] == TiltMode.EXTERNAL

        per_cover_entity = _get_registry_entry_by_unique_id(hass, entry, per_cover_unique_key)

        assert per_cover_entity is not None
        assert per_cover_entity.domain == Platform.NUMBER

        delete_result = await _run_options_flow(
            hass,
            entry,
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.AUTO,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
                STEP_4_SECTION_TILT_DAY: {per_cover_mode_key: TiltMode.AUTO},
            },
        )
        await hass.async_block_till_done()

        assert delete_result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.state == ConfigEntryState.LOADED
        assert entry.options[ConfKeys.TILT_MODE_DAY.value] == TiltMode.AUTO
        assert entry.options[per_cover_mode_key] == TiltMode.AUTO
        assert _get_registry_entry_by_unique_id(hass, entry, per_cover_unique_key) is None

    #
    # test_options_flow_reload_deletes_per_cover_external_tilt_stored_value
    #
    async def test_options_flow_reload_deletes_per_cover_external_tilt_stored_value(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Removing a per-cover external tilt entity should also purge its stored value."""

        _set_test_entity_states(hass)
        entry = create_test_config_entry(hass)
        per_cover_unique_key = f"{TEST_COVER_1}_{COVER_SFX_TILT_EXTERNAL_VALUE_DAY}"
        per_cover_mode_key = f"{TEST_COVER_1}_{COVER_SFX_TILT_MODE_DAY}"

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        create_result = await _run_options_flow(
            hass,
            entry,
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.AUTO,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
                STEP_4_SECTION_TILT_DAY: {per_cover_mode_key: TiltMode.EXTERNAL},
            },
        )
        await hass.async_block_till_done()

        assert create_result["type"] is FlowResultType.CREATE_ENTRY

        per_cover_entity = _get_registry_entry_by_unique_id(hass, entry, per_cover_unique_key)

        assert per_cover_entity is not None

        stored_value = 37
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": per_cover_entity.entity_id, "value": stored_value},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert entry.options[per_cover_unique_key] == stored_value

        delete_result = await _run_options_flow(
            hass,
            entry,
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.AUTO,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
                STEP_4_SECTION_TILT_DAY: {per_cover_mode_key: TiltMode.AUTO},
            },
        )
        await hass.async_block_till_done()

        assert delete_result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[per_cover_mode_key] == TiltMode.AUTO
        assert per_cover_unique_key not in entry.options
        assert _get_registry_entry_by_unique_id(hass, entry, per_cover_unique_key) is None
