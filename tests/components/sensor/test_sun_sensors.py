"""Tests for sun position sensors.

This module contains comprehensive tests for the sun azimuth and elevation sensors,
which report the current sun position from the coordinator.

Coverage targets:
- SunAzimuthSensor with valid data
- SunAzimuthSensor with missing data (else branch)
- SunElevationSensor with valid data
- SunElevationSensor with missing data (else branch)
"""

from __future__ import annotations

import pytest

from custom_components.smart_cover_automation.sensor import (
    SunAzimuthSensor,
    SunElevationSensor,
)


@pytest.mark.parametrize(
    "sun_azimuth_value",
    [
        0.0,
        45.5,
        90.0,
        180.0,
        270.0,
        359.9,
    ],
)
async def test_sun_azimuth_sensor_with_valid_data(mock_coordinator_basic, sun_azimuth_value: float) -> None:
    """Test sun azimuth sensor returns value when data is available.

    This parametrized test verifies that the sensor correctly returns the sun azimuth
    angle from the coordinator data.

    Coverage target: sensor.py SunAzimuthSensor native_value with data
    """
    # Set coordinator data with sun_azimuth
    mock_coordinator_basic.data = {
        "sun_azimuth": sun_azimuth_value,
        "covers": {},
    }

    # Create sensor instance
    sensor = SunAzimuthSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns the correct azimuth value
    assert native_value == sun_azimuth_value
    assert isinstance(native_value, float)


@pytest.mark.parametrize(
    "coordinator_data",
    [
        None,  # No data at all
        {},  # Empty data dict
        {"covers": {}},  # Valid data but missing sun_azimuth key
        {"sun_elevation": 45.0},  # Data with different key
    ],
)
async def test_sun_azimuth_sensor_with_missing_data(mock_coordinator_basic, coordinator_data) -> None:
    """Test sun azimuth sensor returns None when data is unavailable.

    This parametrized test verifies that the sensor handles various missing data
    scenarios by returning None.

    Coverage target: sensor.py line 205-208 (SunAzimuthSensor else branch)
    """
    # Set coordinator data (or None)
    mock_coordinator_basic.data = coordinator_data

    # Create sensor instance
    sensor = SunAzimuthSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns None when data is missing
    assert native_value is None


@pytest.mark.parametrize(
    "sun_elevation_value",
    [
        -90.0,  # Nadir (sun directly below)
        -45.0,
        0.0,  # Horizon
        30.0,
        45.0,
        90.0,  # Zenith (sun directly above)
    ],
)
async def test_sun_elevation_sensor_with_valid_data(mock_coordinator_basic, sun_elevation_value: float) -> None:
    """Test sun elevation sensor returns value when data is available.

    This parametrized test verifies that the sensor correctly returns the sun elevation
    angle from the coordinator data.

    Coverage target: sensor.py SunElevationSensor native_value with data
    """
    # Set coordinator data with sun_elevation
    mock_coordinator_basic.data = {
        "sun_elevation": sun_elevation_value,
        "covers": {},
    }

    # Create sensor instance
    sensor = SunElevationSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns the correct elevation value
    assert native_value == sun_elevation_value
    assert isinstance(native_value, float)


@pytest.mark.parametrize(
    "coordinator_data",
    [
        None,  # No data at all
        {},  # Empty data dict
        {"covers": {}},  # Valid data but missing sun_elevation key
        {"sun_azimuth": 180.0},  # Data with different key
    ],
)
async def test_sun_elevation_sensor_with_missing_data(mock_coordinator_basic, coordinator_data) -> None:
    """Test sun elevation sensor returns None when data is unavailable.

    This parametrized test verifies that the sensor handles various missing data
    scenarios by returning None.

    Coverage target: sensor.py line 241-244 (SunElevationSensor else branch)
    """
    # Set coordinator data (or None)
    mock_coordinator_basic.data = coordinator_data

    # Create sensor instance
    sensor = SunElevationSensor(mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns None when data is missing
    assert native_value is None


async def test_sun_azimuth_sensor_entity_properties(mock_coordinator_basic) -> None:
    """Test sun azimuth sensor has correct entity properties.

    Verifies that the sensor is properly configured with expected attributes.
    """
    # Create sensor instance
    sensor = SunAzimuthSensor(mock_coordinator_basic)

    # Verify entity description properties
    assert sensor.entity_description.key == "sun_azimuth"
    assert sensor.entity_description.translation_key == "sun_azimuth"
    assert sensor.entity_description.icon == "mdi:sun-compass"
    assert sensor.entity_description.native_unit_of_measurement == "°"

    # Verify unique ID
    assert sensor.unique_id == "smart_cover_automation_sun_azimuth"


async def test_sun_elevation_sensor_entity_properties(mock_coordinator_basic) -> None:
    """Test sun elevation sensor has correct entity properties.

    Verifies that the sensor is properly configured with expected attributes.
    """
    # Create sensor instance
    sensor = SunElevationSensor(mock_coordinator_basic)

    # Verify entity description properties
    assert sensor.entity_description.key == "sun_elevation"
    assert sensor.entity_description.translation_key == "sun_elevation"
    assert sensor.entity_description.icon == "mdi:sun-angle-outline"
    assert sensor.entity_description.native_unit_of_measurement == "°"

    # Verify unique ID
    assert sensor.unique_id == "smart_cover_automation_sun_elevation"


async def test_sun_sensors_availability(mock_coordinator_basic) -> None:
    """Test sun sensors inherit availability from coordinator.

    Verifies that sensors correctly report availability based on coordinator state.
    """
    # Test with successful update
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.data = {"sun_azimuth": 180.0, "sun_elevation": 45.0}

    azimuth_sensor = SunAzimuthSensor(mock_coordinator_basic)
    elevation_sensor = SunElevationSensor(mock_coordinator_basic)

    assert azimuth_sensor.available is True
    assert elevation_sensor.available is True

    # Test with failed update
    mock_coordinator_basic.last_update_success = False

    assert azimuth_sensor.available is False
    assert elevation_sensor.available is False
