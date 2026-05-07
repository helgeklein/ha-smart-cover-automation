"""Parameterized tests for sensor entities.

This module provides comprehensive parameterized tests for all data-based
and config-based sensor entities, eliminating code duplication while ensuring
complete test coverage.

Sensors tested:
- SunAzimuthSensor (data-based)
- SunElevationSensor (data-based)
- TempCurrentMaxSensor (data-based)
- EveningClosureTimeSensor (config-based)

Note: AutomationDisabledTimeRangeSensor has unique complex behavior and is
tested separately in test_automation_disabled_time_range.py
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.data import CoordinatorData
from custom_components.smart_cover_automation.sensor import (
    EveningClosureModeSensor,
    EveningClosureTimeSensor,
    MorningOpeningModeSensor,
    MorningOpeningTimeSensor,
    SunAzimuthSensor,
    SunElevationSensor,
    TempCurrentMaxSensor,
)
from tests.conftest import set_test_options

if TYPE_CHECKING:
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


# Configuration for all sensors to be tested
SENSOR_CONFIGS = [
    {
        "sensor_class": SunAzimuthSensor,
        "key": "sun_azimuth",
        "translation_key": "sun_azimuth",
        "data_attribute": "sun_azimuth",
        "icon": "mdi:sun-compass",
        "native_unit_of_measurement": "°",
        "device_class": None,
        "type": "data_based",
        "test_values": [0.0, 45.5, 90.0, 180.0, 270.0, 359.9],
    },
    {
        "sensor_class": SunElevationSensor,
        "key": "sun_elevation",
        "translation_key": "sun_elevation",
        "data_attribute": "sun_elevation",
        "icon": "mdi:sun-angle-outline",
        "native_unit_of_measurement": "°",
        "device_class": None,
        "type": "data_based",
        "test_values": [-90.0, -45.0, 0.0, 30.0, 45.0, 90.0],
    },
    {
        "sensor_class": TempCurrentMaxSensor,
        "key": "temp_current_max",
        "translation_key": "temp_current_max",
        "data_attribute": "temp_current_max",
        "icon": "mdi:thermometer-chevron-up",
        "native_unit_of_measurement": "°C",
        "device_class": "temperature",
        "type": "data_based",
        "test_values": [0.0, 15.5, 20.0, 25.3, 30.0, 35.7],
    },
    {
        "sensor_class": EveningClosureTimeSensor,
        "key": "close_covers_after_sunset_delay",
        "translation_key": "close_covers_after_sunset_delay",
        "icon": "mdi:timer-outline",
        "native_unit_of_measurement": None,
        "device_class": None,
        "type": "config_based",
        # Test values as (config_time, expected_string)
        "test_values": [
            (time(0, 1, 0), "00:01"),
            (time(0, 5, 0), "00:05"),
            (time(0, 10, 0), "00:10"),
            (time(0, 30, 0), "00:30"),
            (time(1, 0, 0), "01:00"),
        ],
    },
]


#
# test_sensor_entity_properties
#
@pytest.mark.parametrize("config", SENSOR_CONFIGS, ids=lambda c: c["key"])
async def test_sensor_entity_properties(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that sensor has correct entity properties.

    Verifies key, translation_key, icon, unit_of_measurement, and device_class.
    """
    sensor = config["sensor_class"](mock_coordinator_basic)

    assert sensor.entity_description.key == config["key"]
    assert sensor.entity_description.translation_key == config["translation_key"]
    assert sensor.entity_description.icon == config["icon"]
    assert sensor.entity_description.native_unit_of_measurement == config["native_unit_of_measurement"]
    if config["device_class"]:
        assert sensor.entity_description.device_class == config["device_class"]


#
# test_sensor_unique_id
#
@pytest.mark.parametrize("config", SENSOR_CONFIGS, ids=lambda c: c["key"])
async def test_sensor_unique_id(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that sensor has correct unique_id format."""
    sensor = config["sensor_class"](mock_coordinator_basic)

    expected_unique_id = f"{mock_coordinator_basic.config_entry.entry_id}_{config['key']}"
    assert sensor.unique_id == expected_unique_id


#
# test_sensor_availability
#
@pytest.mark.parametrize("config", SENSOR_CONFIGS, ids=lambda c: c["key"])
async def test_sensor_availability(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that sensor availability tracks coordinator availability.

    Verifies that sensors correctly delegate availability to the
    coordinator's last_update_success property.
    """
    sensor = config["sensor_class"](mock_coordinator_basic)

    # Test with coordinator available
    mock_coordinator_basic.last_update_success = True
    assert sensor.available is True

    # Test with coordinator unavailable
    mock_coordinator_basic.last_update_success = False
    assert sensor.available is False


#
# test_data_based_sensor_with_valid_data
#
def _data_value_id(val):
    """Generate test ID for data-based sensor value tests."""
    if isinstance(val, tuple) and len(val) == 2:
        return f"{val[0]['key']}_{val[1]}"
    return str(val)


@pytest.mark.parametrize(
    "config,test_value",
    [(config, value) for config in SENSOR_CONFIGS if config["type"] == "data_based" for value in config["test_values"]],
    ids=_data_value_id,
)
async def test_data_based_sensor_with_valid_data(
    mock_coordinator_basic: DataUpdateCoordinator,
    config: dict[str, Any],
    test_value: float,
) -> None:
    """Test data-based sensor returns value when data is available.

    This parametrized test verifies that data-based sensors correctly return
    values from the coordinator data.
    """
    # Set coordinator data with the specific attribute
    data_kwargs = {"covers": {}, config["data_attribute"]: test_value}
    mock_coordinator_basic.data = CoordinatorData(**data_kwargs)

    # Create sensor instance
    sensor = config["sensor_class"](mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns the correct value
    assert native_value == test_value
    assert isinstance(native_value, float)


#
# test_data_based_sensor_with_missing_data
#
def _missing_data_id(val):
    """Generate test ID for missing data tests."""
    if isinstance(val, tuple) and len(val) == 2:
        config, data = val
        if data is None:
            return f"{config['key']}_None"
        if isinstance(data, CoordinatorData):
            return f"{config['key']}_missing"
    return str(val)


@pytest.mark.parametrize(
    "config,coordinator_data",
    [
        (config, data)
        for config in SENSOR_CONFIGS
        if config["type"] == "data_based"
        for data in [
            None,  # No data at all
            CoordinatorData(covers={}),  # Empty data (missing attribute)
        ]
    ],
    ids=_missing_data_id,
)
async def test_data_based_sensor_with_missing_data(
    mock_coordinator_basic: DataUpdateCoordinator,
    config: dict[str, Any],
    coordinator_data: CoordinatorData | None,
) -> None:
    """Test data-based sensor returns None when data is unavailable.

    This parametrized test verifies that data-based sensors handle various
    missing data scenarios by returning None.
    """
    # Set coordinator data (or None)
    mock_coordinator_basic.data = coordinator_data  # type: ignore[assignment]

    # Create sensor instance
    sensor = config["sensor_class"](mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns None when data is missing
    assert native_value is None


#
# test_config_based_sensor_values
#
def _config_value_id(val):
    """Generate test ID for config-based sensor value tests."""
    if isinstance(val, tuple) and len(val) == 2:
        config, value_pair = val
        if isinstance(value_pair, tuple) and len(value_pair) == 2:
            return f"{config['key']}_{value_pair[0]}_{value_pair[1]}"
    return str(val)


@pytest.mark.parametrize(
    "config,test_value_pair",
    [(config, value_pair) for config in SENSOR_CONFIGS if config["type"] == "config_based" for value_pair in config["test_values"]],
    ids=_config_value_id,
)
async def test_config_based_sensor_values(
    mock_coordinator_basic: DataUpdateCoordinator,
    config: dict[str, Any],
    test_value_pair: tuple[time, str],
) -> None:
    """Test config-based sensor returns correct converted value.

    For EveningClosureTimeSensor, this tests the conversion
    from time object (stored in config) to HH:MM string (displayed value).
    """
    config_time, expected_string = test_value_pair

    # Create mock for _resolved_settings
    mock_settings = MagicMock()
    mock_settings.evening_closure_time = config_time
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)

    # Create sensor instance
    sensor = config["sensor_class"](mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify sensor returns correctly converted value
    assert native_value == expected_string
    assert isinstance(native_value, str)


#
# test_sensor_coordinator_integration
#
@pytest.mark.parametrize("config", SENSOR_CONFIGS, ids=lambda c: c["key"])
async def test_sensor_coordinator_integration(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that sensor is properly linked to coordinator.

    Verifies that each sensor entity receives and stores the coordinator
    instance correctly.
    """
    sensor = config["sensor_class"](mock_coordinator_basic)

    assert sensor.coordinator is mock_coordinator_basic


#
# test_data_based_sensor_type_validation
#
@pytest.mark.parametrize(
    "config",
    [c for c in SENSOR_CONFIGS if c["type"] == "data_based"],
    ids=lambda c: c["key"],
)
async def test_data_based_sensor_type_validation(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that data-based sensors return correct data types.

    Verifies that when data is available, sensors return the expected type
    (float for numeric sensors).
    """
    # Set coordinator data with a test value
    test_value = config["test_values"][0]
    data_kwargs = {"covers": {}, config["data_attribute"]: test_value}
    mock_coordinator_basic.data = CoordinatorData(**data_kwargs)

    # Create sensor instance
    sensor = config["sensor_class"](mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify type
    assert isinstance(native_value, float)


#
# test_config_based_sensor_type_validation
#
@pytest.mark.parametrize(
    "config",
    [c for c in SENSOR_CONFIGS if c["type"] == "config_based"],
    ids=lambda c: c["key"],
)
async def test_config_based_sensor_type_validation(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that config-based sensors return correct data types.

    Verifies that config-based sensors return the expected type
    (str for EveningClosureTimeSensor).
    """
    # Set up mock settings with first test value
    config_time, expected_string = config["test_values"][0]
    mock_settings = MagicMock()
    mock_settings.evening_closure_time = config_time
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)

    # Create sensor instance
    sensor = config["sensor_class"](mock_coordinator_basic)

    # Get native value
    native_value = sensor.native_value

    # Verify type
    assert isinstance(native_value, str)


#
# test_evening_closure_time_sensor_boundary_values
#
async def test_evening_closure_time_sensor_boundary_values(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test EveningClosureTimeSensor with boundary values.

    Tests edge cases like zero time, various time values, etc.
    """
    test_cases = [
        (time(0, 0, 0), "00:00"),  # Zero
        (time(0, 0, 30), "00:00"),  # Seconds only — displayed as HH:MM
        (time(0, 0, 59), "00:00"),  # Just under 1 minute
        (time(2, 0, 0), "02:00"),  # 2 hours
        (time(23, 59, 0), "23:59"),  # Max practical value
    ]

    for config_time, expected_string in test_cases:
        # Set up mock settings
        mock_settings = MagicMock()
        mock_settings.evening_closure_time = config_time
        mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)

        # Create sensor instance
        sensor = EveningClosureTimeSensor(mock_coordinator_basic)

        # Verify conversion
        assert sensor.native_value == expected_string


async def test_evening_closure_time_sensor_uses_external_value_in_external_mode(
    mock_coordinator_basic: DataUpdateCoordinator,
) -> None:
    """External evening closure mode should surface the externally supplied time."""

    mock_settings = MagicMock()
    mock_settings.evening_closure_mode = const.EveningClosureMode.EXTERNAL
    mock_settings.evening_closure_time = time(0, 15, 0)
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)
    set_test_options(
        mock_coordinator_basic.config_entry,
        {const.TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME: "18:45:00"},
    )

    sensor = EveningClosureTimeSensor(mock_coordinator_basic)

    assert sensor.native_value == "18:45"


async def test_evening_closure_time_sensor_returns_none_for_invalid_external_value(
    mock_coordinator_basic: DataUpdateCoordinator,
) -> None:
    """Invalid external evening closure times should not fall back to the ignored base value."""

    mock_settings = MagicMock()
    mock_settings.evening_closure_mode = const.EveningClosureMode.EXTERNAL
    mock_settings.evening_closure_time = time(0, 15, 0)
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)
    set_test_options(
        mock_coordinator_basic.config_entry,
        {const.TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME: "not-a-time"},
    )

    sensor = EveningClosureTimeSensor(mock_coordinator_basic)

    assert sensor.native_value is None


async def test_morning_opening_time_sensor_properties(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Morning opening time sensor should expose the expected metadata."""

    sensor = MorningOpeningTimeSensor(mock_coordinator_basic)

    assert sensor.entity_description.key == const.SENSOR_KEY_MORNING_OPENING_TIME
    assert sensor.entity_description.translation_key == const.SENSOR_KEY_MORNING_OPENING_TIME
    assert sensor.entity_description.icon == "mdi:timer-outline"
    assert sensor.unique_id == f"{mock_coordinator_basic.config_entry.entry_id}_{const.SENSOR_KEY_MORNING_OPENING_TIME}"


async def test_morning_opening_mode_sensor_properties(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Morning opening mode sensor should expose the expected metadata."""

    sensor = MorningOpeningModeSensor(mock_coordinator_basic)

    assert sensor.entity_description.key == const.SENSOR_KEY_MORNING_OPENING_MODE
    assert sensor.entity_description.translation_key == const.SENSOR_KEY_MORNING_OPENING_MODE
    assert sensor.entity_description.icon == "mdi:clock-time-eight"
    assert sensor.unique_id == f"{mock_coordinator_basic.config_entry.entry_id}_{const.SENSOR_KEY_MORNING_OPENING_MODE}"


async def test_morning_opening_time_sensor_uses_resolved_time_when_not_external(
    mock_coordinator_basic: DataUpdateCoordinator,
) -> None:
    """Non-external morning opening modes should expose the configured base time."""

    mock_settings = MagicMock()
    mock_settings.morning_opening_mode = const.MorningOpeningMode.FIXED_TIME
    mock_settings.morning_opening_time = time(7, 30, 0)
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)

    sensor = MorningOpeningTimeSensor(mock_coordinator_basic)

    assert sensor.native_value == "07:30"


async def test_morning_opening_time_sensor_uses_external_value_in_external_mode(
    mock_coordinator_basic: DataUpdateCoordinator,
) -> None:
    """External morning opening mode should surface the externally supplied time."""

    mock_settings = MagicMock()
    mock_settings.morning_opening_mode = const.MorningOpeningMode.EXTERNAL
    mock_settings.morning_opening_time = time(8, 0, 0)
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)
    set_test_options(
        mock_coordinator_basic.config_entry,
        {const.TIME_KEY_MORNING_OPENING_EXTERNAL_TIME: "07:45:00"},
    )

    sensor = MorningOpeningTimeSensor(mock_coordinator_basic)

    assert sensor.native_value == "07:45"


async def test_morning_opening_time_sensor_returns_none_for_invalid_external_value(
    mock_coordinator_basic: DataUpdateCoordinator,
) -> None:
    """Invalid external morning opening times should not fall back to the ignored base value."""

    mock_settings = MagicMock()
    mock_settings.morning_opening_mode = const.MorningOpeningMode.EXTERNAL
    mock_settings.morning_opening_time = time(8, 0, 0)
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)
    set_test_options(
        mock_coordinator_basic.config_entry,
        {const.TIME_KEY_MORNING_OPENING_EXTERNAL_TIME: "not-a-time"},
    )

    sensor = MorningOpeningTimeSensor(mock_coordinator_basic)

    assert sensor.native_value is None


async def test_mode_sensors_return_resolved_modes(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Evening and morning mode sensors should mirror resolved configuration modes."""

    mock_settings = MagicMock()
    mock_settings.evening_closure_mode = const.EveningClosureMode.EXTERNAL
    mock_settings.morning_opening_mode = const.MorningOpeningMode.RELATIVE_TO_SUNRISE
    mock_coordinator_basic._resolved_settings = MagicMock(return_value=mock_settings)

    evening_sensor = EveningClosureModeSensor(mock_coordinator_basic)
    morning_sensor = MorningOpeningModeSensor(mock_coordinator_basic)

    assert evening_sensor.native_value == const.EveningClosureMode.EXTERNAL
    assert morning_sensor.native_value == const.MorningOpeningMode.RELATIVE_TO_SUNRISE
