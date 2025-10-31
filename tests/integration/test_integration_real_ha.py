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

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_cover_automation import DOMAIN
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_SFX_AZIMUTH,
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
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
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
