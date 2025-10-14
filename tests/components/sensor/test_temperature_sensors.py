"""Tests for temperature sensors.

This module contains comprehensive tests for the temperature sensors,
which report current max temperature and configured threshold temperature.

Coverage targets:
- TempCurrentMaxSensor with valid data
- TempCurrentMaxSensor with missing data (else branch)
- TempThresholdSensor returning configured value
"""

from __future__ import annotations

import pytest

from custom_components.smart_cover_automation.sensor import (
    TempCurrentMaxSensor,
    TempThresholdSensor,
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
    mock_coordinator_basic.data = {
        "temp_current_max": temp_value,
        "covers": {},
    }

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
        {},  # Empty data dict
        {"covers": {}},  # Valid data but missing temp_current_max key
        {"sun_elevation": 45.0},  # Data with different key
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


@pytest.mark.parametrize(
    "threshold_value",
    [
        15.0,
        20.0,
        25.0,
        30.0,
    ],
)
async def test_temp_threshold_sensor_returns_configured_value(mock_config_entry, mock_coordinator_basic, threshold_value: float) -> None:
    """Test temp threshold sensor returns the configured threshold value.

    This parametrized test verifies that the sensor correctly retrieves
    the configured temperature threshold from resolved settings.

    Coverage target: sensor.py lines 316-317 (TempThresholdSensor native_value)
    """
    # Set the threshold in config entry options
    mock_config_entry.options = {"temp_threshold": threshold_value}
    mock_coordinator_basic.config_entry = mock_config_entry

    # Create sensor instance
    sensor = TempThresholdSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns the configured threshold
    assert native_value == threshold_value
    assert isinstance(native_value, float)


async def test_temp_threshold_sensor_uses_default_when_not_configured(mock_config_entry, mock_coordinator_basic) -> None:
    """Test temp threshold sensor returns default value when not configured.

    This test verifies that when no threshold is configured in options,
    the sensor returns the default value from the configuration registry.

    Coverage target: sensor.py lines 316-317 (TempThresholdSensor native_value)
    """
    # Clear options so default is used
    mock_config_entry.options = {}
    mock_coordinator_basic.config_entry = mock_config_entry

    # Create sensor instance
    sensor = TempThresholdSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns a value (the default from config registry)
    assert native_value is not None
    assert isinstance(native_value, float)
    # Default value should be 23.0 based on config.py
    assert native_value == 23.0


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


async def test_temp_threshold_sensor_entity_properties(mock_coordinator_basic) -> None:
    """Test TempThresholdSensor has correct entity properties.

    Verifies that the sensor is properly configured with correct device class,
    unit of measurement, and other entity properties.
    """
    sensor = TempThresholdSensor(mock_coordinator_basic)

    # Check entity description properties
    assert sensor.entity_description.key == "temp_threshold"
    assert sensor.entity_description.translation_key == "temp_threshold"
    assert sensor.entity_description.device_class == "temperature"
    assert sensor.entity_description.native_unit_of_measurement == "°C"
    assert sensor.entity_description.icon == "mdi:thermometer-lines"

    # Check unique_id follows expected pattern
    assert sensor.unique_id == "smart_cover_automation_temp_threshold"


async def test_temp_sensors_availability(mock_coordinator_basic) -> None:
    """Test temperature sensors availability tracks coordinator availability.

    Verifies that both temperature sensors correctly delegate availability
    to the coordinator's last_update_success property.
    """
    # Test with coordinator available
    mock_coordinator_basic.last_update_success = True

    temp_current_sensor = TempCurrentMaxSensor(mock_coordinator_basic)
    temp_threshold_sensor = TempThresholdSensor(mock_coordinator_basic)

    assert temp_current_sensor.available is True
    assert temp_threshold_sensor.available is True

    # Test with coordinator unavailable
    mock_coordinator_basic.last_update_success = False

    assert temp_current_sensor.available is False
    assert temp_threshold_sensor.available is False
