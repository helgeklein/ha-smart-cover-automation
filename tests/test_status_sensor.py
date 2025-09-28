"""Tests for the Automation Status sensor.

This module contains comprehensive tests for the Smart Cover Automation status sensor,
which provides users with real-time visibility into the automation system's current
state and activity. The status sensor is a critical user interface component that
displays human-readable summaries and detailed attributes about the automation.

Key testing areas include:
1. **Summary Generation**: Tests human-readable status text creation that summarizes
   current automation activity, cover positions, and environmental conditions
2. **Attribute Exposure**: Tests comprehensive state attributes that provide detailed
   information for automation dashboards and debugging
3. **Combined Mode Operation**: Tests unified temperature and sun automation status
4. **Environmental Data Integration**: Tests temperature and sun position reporting
5. **Cover Movement Tracking**: Tests counting and reporting of covers being moved
6. **Disabled State Handling**: Tests proper status reporting when automation is disabled

The status sensor serves multiple purposes:
- **User Visibility**: Provides at-a-glance understanding of automation activity
- **Debugging Aid**: Exposes internal state for troubleshooting configuration issues
- **Dashboard Integration**: Supplies data for Home Assistant dashboards and automations
- **Historical Tracking**: Enables logging and analysis of automation behavior over time

These tests ensure the status sensor accurately reflects the automation system's
state and provides meaningful information to users regardless of configuration
or environmental conditions.
"""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_ATTR_POS_CURRENT,
    COVER_ATTR_POS_TARGET_FINAL,
    SENSOR_ATTR_AUTOMATION_ENABLED,
    SENSOR_ATTR_COVERS_MIN_POSITION_DELTA,
    SENSOR_ATTR_COVERS_NUM_MOVED,
    SENSOR_ATTR_COVERS_NUM_TOTAL,
    SENSOR_ATTR_SIMULATION_ENABLED,
    SENSOR_ATTR_SUN_AZIMUTH,
    SENSOR_ATTR_SUN_ELEVATION,
    SENSOR_ATTR_SUN_ELEVATION_THRESH,
    SENSOR_ATTR_TEMP_CURRENT,
    SENSOR_ATTR_TEMP_THRESHOLD,
    SENSOR_KEY_AUTOMATION_STATUS,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)

from .conftest import (
    TEST_COMFORTABLE_TEMP_2,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    MockConfigEntry,
    create_sun_config,
    create_temperature_config,
)


async def _capture_entities(hass: HomeAssistant, config: dict[str, object]) -> list[Entity]:
    """Helper function to set up the sensor platform and capture created entities.

    This utility function streamlines the test setup process by:
    1. Creating a mock config entry with the provided configuration
    2. Setting up a coordinator with successful state
    3. Executing the sensor platform setup process
    4. Capturing and returning all created entities

    This pattern is reused across multiple tests to ensure consistent
    setup and reduce code duplication while testing various sensor scenarios.

    Args:
        hass: Mock Home Assistant instance
        config: Configuration dictionary for the integration

    Returns:
        List of entities created by the sensor platform
    """
    hass_mock = cast(MagicMock, hass)
    entry = MockConfigEntry(config)

    # Setup coordinator with basic successful state
    coordinator = DataUpdateCoordinator(hass_mock, cast(IntegrationConfigEntry, entry))
    coordinator.data = {}
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    entry.runtime_data.coordinator = coordinator

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Execute platform setup to create sensor entities
    await async_setup_entry_sensor(hass_mock, cast(IntegrationConfigEntry, entry), add_entities)

    return captured


def _get_status_entity(entities: list[Entity]) -> Entity:
    """Helper function to extract the automation status sensor from a list of entities.

    Finds and returns the automation status sensor entity by matching its
    entity description key. This helper ensures tests can reliably access
    the specific sensor they need to test.

    Args:
        entities: List of entities to search through

    Returns:
        The automation status sensor entity

    Raises:
        StopIteration: If no status sensor is found in the entity list
    """
    return next(e for e in entities if getattr(getattr(e, "entity_description"), "key", "") == SENSOR_KEY_AUTOMATION_STATUS)


@pytest.mark.asyncio
async def test_status_sensor_combined_summary_and_attributes() -> None:
    """Test status sensor summary generation and attribute exposure for temperature automation.

    This test verifies that the automation status sensor correctly generates
    human-readable summaries and exposes comprehensive state attributes when
    operating in temperature-based automation mode.

    Test scenario:
    - Temperature-based automation configuration
    - Two covers: one moving (50% → 40%), one stationary (100% → 100%)
    - Current temperature: 22.5°C (comfortable range)
    - Custom configuration values for hysteresis and position delta

    Expected behavior:
    - Summary includes temperature information and cover movement count
    - Attributes expose all relevant configuration and state values
    - Cover movement tracking shows 1 out of 2 covers moving

    This test ensures users can see automation activity at a glance and access
    detailed information for troubleshooting and dashboard integration.
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    # Add custom tuning/options to test attribute exposure
    config[ConfKeys.COVERS_MIN_POSITION_DELTA.value] = 10

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Simulate coordinator data with realistic automation scenario
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.data = {
        SENSOR_ATTR_TEMP_CURRENT: 22.5,  # Current temperature reading
        ConfKeys.COVERS.value: {
            "cover.one": {
                ATTR_CURRENT_POSITION: 50,  # Current position: 50%
                COVER_ATTR_POS_CURRENT: 50,  # Current position in SCA format
                COVER_ATTR_POS_TARGET_FINAL: 40,  # Target position: 40% (movement required)
            },
            "cover.two": {
                ATTR_CURRENT_POSITION: 100,  # Current position: 100% (fully open)
                COVER_ATTR_POS_CURRENT: 100,  # Current position in SCA format
                COVER_ATTR_POS_TARGET_FINAL: 100,  # Target position: 100% (no movement)
            },
        },
    }

    # Verify summary string contains expected information
    summary = cast(str, getattr(status, "native_value"))
    assert "Temp " in summary  # Temperature information present
    assert TEST_COMFORTABLE_TEMP_2 in summary  # Comfortable temperature reference
    assert "moves 1/2" in summary  # Cover movement count (1 out of 2)

    # Verify comprehensive state attributes are exposed
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs[SENSOR_ATTR_AUTOMATION_ENABLED] is True  # Automation is enabled
    assert attrs[SENSOR_ATTR_COVERS_NUM_TOTAL] == 2  # Total cover count
    assert attrs[SENSOR_ATTR_COVERS_NUM_MOVED] == 1  # Covers being moved
    assert attrs[SENSOR_ATTR_COVERS_MIN_POSITION_DELTA] == 10  # Minimum position change threshold
    assert attrs[SENSOR_ATTR_TEMP_THRESHOLD] == config[ConfKeys.TEMP_THRESHOLD.value]  # Temperature threshold
    assert attrs[SENSOR_ATTR_TEMP_CURRENT] == 22.5  # Current temperature
    assert isinstance(attrs[ConfKeys.COVERS.value], dict)  # Covers data structure


@pytest.mark.asyncio
async def test_status_sensor_combined_sun_attributes_present() -> None:
    """Test status sensor summary and attributes for sun-based automation.

    This test verifies that the automation status sensor correctly incorporates
    sun position information when operating with sun-based automation logic.
    The sensor should display sun elevation and azimuth data in both the
    summary text and detailed attributes.

    Test scenario:
    - Sun-based automation configuration
    - Two covers: one moving (100% → 80%), one stationary (100% → 100%)
    - High sun elevation (above threshold for automation activation)
    - Direct sun azimuth (aligned with cover direction)

    Expected behavior:
    - Summary includes sun elevation information
    - Summary shows cover movement count (1 out of 2 covers)
    - Attributes expose sun elevation, azimuth, and threshold values
    - All configuration parameters are properly exposed

    This test ensures users can monitor sun-based automation and understand
    why covers are moving based on solar position and intensity.
    """
    # Setup mock Home Assistant environment for sun automation
    hass = MagicMock(spec=HomeAssistant)
    config = create_sun_config()
    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Simulate coordinator data with sun position and cover states
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.data = {
        SENSOR_ATTR_SUN_ELEVATION: TEST_HIGH_ELEVATION,  # Sun elevation above threshold
        SENSOR_ATTR_SUN_AZIMUTH: TEST_DIRECT_AZIMUTH,  # Sun azimuth aligned with covers
        ConfKeys.COVERS.value: {
            "cover.one": {
                ATTR_CURRENT_POSITION: 100,  # Currently fully open
                COVER_ATTR_POS_CURRENT: 100,  # Current position in SCA format
                COVER_ATTR_POS_TARGET_FINAL: 80,  # Target: partially closed (sun protection)
            },
            "cover.two": {
                ATTR_CURRENT_POSITION: 100,  # Currently fully open
                COVER_ATTR_POS_CURRENT: 100,  # Current position in SCA format
                COVER_ATTR_POS_TARGET_FINAL: 100,  # Target: remain open (no direct sun)
            },
        },
    }

    # Verify summary string includes sun information
    summary = cast(str, getattr(status, "native_value"))
    # Summary should include Sun elevation when sun automation is active
    assert f"Sun elev {TEST_HIGH_ELEVATION}°" in summary  # Sun elevation display
    assert "moves 1/2" in summary  # Cover movement count

    # Verify sun-specific attributes are exposed
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs[SENSOR_ATTR_AUTOMATION_ENABLED] is True  # Automation enabled
    assert attrs[SENSOR_ATTR_COVERS_NUM_TOTAL] == 2  # Total cover count
    assert attrs[SENSOR_ATTR_COVERS_NUM_MOVED] == 1  # Covers being moved
    assert attrs[SENSOR_ATTR_SUN_ELEVATION] == TEST_HIGH_ELEVATION  # Current sun elevation
    assert attrs[SENSOR_ATTR_SUN_AZIMUTH] == TEST_DIRECT_AZIMUTH  # Current sun azimuth
    assert attrs[SENSOR_ATTR_SUN_ELEVATION_THRESH] == config[ConfKeys.SUN_ELEVATION_THRESHOLD.value]  # Elevation threshold
    assert isinstance(attrs[ConfKeys.COVERS.value], dict)  # Covers data structure


@pytest.mark.asyncio
async def test_status_sensor_disabled() -> None:
    """Test status sensor behavior when automation is globally disabled.

    This test verifies that the automation status sensor correctly reports
    'Disabled' status when the automation is turned off globally through
    the enabled configuration option.

    Test scenario:
    - Temperature-based automation configuration
    - Automation globally disabled (enabled = False)
    - Coordinator data present but should be ignored

    Expected behavior:
    - Summary displays 'Disabled' regardless of other data
    - Sensor short-circuits evaluation when automation is disabled
    - No complex processing of cover states or environmental data

    This test ensures users receive clear feedback when automation is
    intentionally disabled, helping them understand why covers aren't
    moving despite environmental conditions that would normally trigger automation.
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    config[ConfKeys.ENABLED.value] = False  # Globally disable automation

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Even with coordinator data present, disabled state should short-circuit evaluation
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.data = {ConfKeys.COVERS.value: {}}  # Minimal data structure

    # Verify sensor reports disabled status
    val = cast(str, getattr(status, "native_value"))
    assert val == "Disabled"


async def test_status_sensor_simulation_mode_enabled() -> None:
    """Test that status sensor properly reports simulation mode when enabled.

    This test verifies that when simulation mode is active, the status sensor:
    1. Includes "Simulation mode enabled" in the summary text
    2. Exposes the simulation_enabled attribute as True
    3. Still reports other automation state correctly

    Simulation mode is important for users to understand when the automation
    is running in test mode without actually moving covers.
    """
    # Setup mock Home Assistant environment with simulation mode enabled
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    config[ConfKeys.SIMULATING.value] = True  # Enable simulation mode

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Setup coordinator with basic automation data
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.data = {
        ConfKeys.COVERS.value: {},
        "temp_current": 22.0,  # Comfortable temperature
    }

    # Verify simulation mode is reported in status summary
    val = cast(str, getattr(status, "native_value"))
    assert "Simulation mode enabled" in val

    # Verify simulation mode attribute is exposed
    attrs = cast(dict[str, object], getattr(status, "extra_state_attributes"))
    assert attrs[SENSOR_ATTR_SIMULATION_ENABLED] is True


async def test_status_sensor_simulation_mode_disabled() -> None:
    """Test that status sensor properly reports when simulation mode is disabled.

    This test verifies that when simulation mode is inactive, the status sensor:
    1. Does NOT include "Simulation mode enabled" in the summary text
    2. Exposes the simulation_enabled attribute as False
    3. Reports normal automation state

    This ensures users can clearly distinguish between normal and simulation operation.
    """
    # Setup mock Home Assistant environment with simulation mode disabled
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    config[ConfKeys.SIMULATING.value] = False  # Explicitly disable simulation mode

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Setup coordinator with basic automation data
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.data = {
        ConfKeys.COVERS.value: {},
        "temp_current": 22.0,  # Comfortable temperature
    }

    # Verify simulation mode is NOT reported in status summary
    val = cast(str, getattr(status, "native_value"))
    assert "Simulation mode enabled" not in val

    # Verify simulation mode attribute is exposed as False
    attrs = cast(dict[str, object], getattr(status, "extra_state_attributes"))
    assert attrs[SENSOR_ATTR_SIMULATION_ENABLED] is False
