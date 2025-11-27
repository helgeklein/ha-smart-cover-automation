"""Tests for temperature sensors.

This module contains comprehensive tests for the temperature sensors,
which report current max temperature.

Coverage targets:
- TempCurrentMaxSensor with valid data
- TempCurrentMaxSensor with missing data (else branch)
"""

from __future__ import annotations

import pytest

from custom_components.smart_cover_automation.data import CoordinatorData
from custom_components.smart_cover_automation.sensor import (
    TempCurrentMaxSensor,
)


@pytest.mark.parametrize(
    "temp_value",
    [
        0.0,
        15.5,
        20.0,
        25.3,
        30.0,
        35.7,
    ],
)
async def test_temp_current_max_sensor_with_valid_data(mock_coordinator_basic, temp_value: float) -> None:
    """Test temp current max sensor returns value when data is available.

    This parametrized test verifies that the sensor correctly returns the
    current maximum temperature from the coordinator data.

    Coverage target: sensor.py TempCurrentMaxSensor native_value with data
    """
    # Set coordinator data with temp_current_max
    mock_coordinator_basic.data = CoordinatorData(
        covers={},
        temp_current_max=temp_value,
    )

    # Create sensor instance
    sensor = TempCurrentMaxSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns the correct temperature value
    assert native_value == temp_value
    assert isinstance(native_value, float)


@pytest.mark.parametrize(
    "coordinator_data",
    [
        None,  # No data at all
        CoordinatorData(covers={}),  # Empty data (missing temp_current_max)
        CoordinatorData(covers={}),  # Valid data but missing temp_current_max key
        CoordinatorData(covers={}, sun_elevation=45.0),  # Data with different key
    ],
)
async def test_temp_current_max_sensor_with_missing_data(mock_coordinator_basic, coordinator_data) -> None:
    """Test temp current max sensor returns None when data is unavailable.

    This parametrized test verifies that the sensor handles various missing data
    scenarios by returning None.

    Coverage target: sensor.py lines 281-284 (TempCurrentMaxSensor else branch)
    """
    # Set coordinator data (or None)
    mock_coordinator_basic.data = coordinator_data

    # Create sensor instance
    sensor = TempCurrentMaxSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns None when data is missing
    assert native_value is None


async def test_temp_current_max_sensor_entity_properties(mock_coordinator_basic) -> None:
    """Test TempCurrentMaxSensor has correct entity properties.

    Verifies that the sensor is properly configured with correct device class,
    unit of measurement, and other entity properties.
    """
    sensor = TempCurrentMaxSensor(mock_coordinator_basic)

    # Check entity description properties
    assert sensor.entity_description.key == "temp_current_max"
    assert sensor.entity_description.translation_key == "temp_current_max"
    assert sensor.entity_description.device_class == "temperature"
    assert sensor.entity_description.native_unit_of_measurement == "°C"
    assert sensor.entity_description.icon == "mdi:thermometer-chevron-up"

    # Check unique_id follows expected pattern
    assert sensor.unique_id == "smart_cover_automation_temp_current_max"


async def test_temp_sensors_availability(mock_coordinator_basic) -> None:
    """Test temperature sensor availability tracks coordinator availability.

    Verifies that the temperature sensor correctly delegates availability
    to the coordinator's last_update_success property.
    """
    # Test with coordinator available
    mock_coordinator_basic.last_update_success = True

    temp_current_sensor = TempCurrentMaxSensor(mock_coordinator_basic)

    assert temp_current_sensor.available is True

    # Test with coordinator unavailable
    mock_coordinator_basic.last_update_success = False

    assert temp_current_sensor.available is False
