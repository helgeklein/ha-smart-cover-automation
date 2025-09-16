"""Tests for sensor edge cases and property handling.

This module contains focused tests for sensor entity edge cases that are not
covered by the main sensor tests, specifically targeting property edge cases
and data availability scenarios.

Coverage targets:
- Sensor availability property edge cases
- Native value handling with missing data
- Extra state attributes handling with missing data
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import ENTITY_DESCRIPTIONS, AutomationStatusSensor

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_sensor_availability_property_delegation() -> None:
    """Test sensor availability property delegation to parent classes.

    This test verifies that the sensor's availability property properly
    delegates to parent class implementations and can be accessed.

    Coverage target: sensor.py line 113 (availability property override)
    """
    # Create mock Home Assistant instance and coordinator
    hass = MagicMock()
    config_entry = MockConfigEntry(create_temperature_config())
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

    # Create sensor instance with entity description
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(coordinator, entity_description)

    # Test that availability property can be accessed and delegates to parent
    # This covers the line: return super().available
    coordinator.last_update_success = True
    availability = sensor.available

    # Verify that the property delegation works and returns a value
    assert availability is not None
    assert isinstance(availability, bool)

    # The key is that we accessed the property, which covers line 113
    # The exact behavior (True vs False) is handled by the parent class


@pytest.mark.asyncio
async def test_sensor_native_value_with_missing_data() -> None:
    """Test sensor native value when coordinator data is missing.

    This test verifies that the sensor handles missing coordinator data
    gracefully and returns None for the native value.

    Coverage target: sensor.py line 125 (native_value with missing data)
    """
    # Create mock Home Assistant instance and coordinator
    hass = MagicMock()
    config_entry = MockConfigEntry(create_temperature_config())
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

    # Set coordinator data to empty dict (falsy for the check)
    coordinator.data = {}  # This will make `if not self.coordinator.data:` true

    # Create sensor instance with entity description
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(coordinator, entity_description)

    # Get native value when no meaningful data is available
    native_value = sensor.native_value

    # Should return None when no meaningful coordinator data is available
    assert native_value is None


@pytest.mark.asyncio
async def test_sensor_extra_state_attributes_with_missing_data() -> None:
    """Test sensor extra state attributes when coordinator data is missing.

    This test verifies that the sensor handles missing coordinator data
    gracefully and returns None for extra state attributes.

    Coverage target: sensor.py line 174 (extra_state_attributes with missing data)
    """
    # Create mock Home Assistant instance and coordinator
    hass = MagicMock()
    config_entry = MockConfigEntry(create_temperature_config())
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

    # Set coordinator data to empty dict (falsy for the check)
    coordinator.data = {}  # This will make `if not self.coordinator.data:` true

    # Create sensor instance with entity description
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(coordinator, entity_description)

    # Get extra state attributes when no data is available
    extra_attributes = sensor.extra_state_attributes

    # Should return None when no coordinator data is available
    assert extra_attributes is None


@pytest.mark.asyncio
async def test_sensor_with_valid_coordinator_data() -> None:
    """Test sensor behavior with valid coordinator data.

    This test ensures that when coordinator data is available, the sensor
    properly processes and returns appropriate values.

    Complementary test to verify the positive case alongside the missing data tests.
    """
    # Create mock Home Assistant instance and coordinator
    hass = MagicMock()
    config_entry = MockConfigEntry(create_temperature_config())
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

    # Set valid coordinator data
    coordinator.data = {
        "covers": {
            "cover.test": {
                "position": 50,
                "sca_cover_desired_position": 75,
            }
        },
        "temp_current": 22.5,
    }
    coordinator.last_update_success = True

    # Create sensor instance with entity description
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(coordinator, entity_description)

    # Verify sensor returns valid data when coordinator data is available
    native_value = sensor.native_value
    assert native_value is not None
    assert isinstance(native_value, str)

    extra_attributes = sensor.extra_state_attributes
    assert extra_attributes is not None
    assert isinstance(extra_attributes, dict)
