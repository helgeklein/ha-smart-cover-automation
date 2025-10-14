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

import pytest

from custom_components.smart_cover_automation.const import (
    COVER_ATTR_POS_TARGET_DESIRED,
)
from custom_components.smart_cover_automation.sensor import LastMovementTimestampSensor


@pytest.mark.parametrize(
    "coordinator_data, last_update_success, expected_result_type",
    [
        ({}, True, type(None)),  # Empty data, successful update - no timestamp
        ({}, False, type(None)),  # Empty data, failed update - no timestamp
        (None, True, type(None)),  # None data, successful update - no timestamp
        (None, False, type(None)),  # None data, failed update - no timestamp
        ({"covers": {}}, True, type(None)),  # Valid data but no movement history - no timestamp
        ({"covers": {}}, False, type(None)),  # Valid data but no movement history - no timestamp
    ],
)
async def test_sensor_native_value_with_various_data_states(
    mock_coordinator_basic, coordinator_data, last_update_success, expected_result_type
) -> None:
    """Test timestamp sensor with various coordinator data states.

    This parametrized test verifies that the sensor handles different combinations
    of coordinator data availability and update success states appropriately.
    The timestamp sensor only returns a value when there's actual movement history.

    Coverage target: sensor.py line 44 (native_value with missing data)
    """
    # Set coordinator data and update status
    mock_coordinator_basic.data = coordinator_data
    mock_coordinator_basic.last_update_success = last_update_success

    # Create sensor instance (entity description is created internally)
    sensor = LastMovementTimestampSensor(mock_coordinator_basic)

    # Get native value (will be None without movement history)
    native_value = sensor.native_value

    # Timestamp sensor always returns None when there's no movement history
    assert native_value is None


@pytest.mark.parametrize(
    "last_update_success, expected_availability",
    [
        (True, True),  # Successful update should be available
        (False, False),  # Failed update should be unavailable
    ],
)
async def test_sensor_availability_property_delegation(mock_coordinator_basic, last_update_success, expected_availability) -> None:
    """Test sensor availability property delegation to parent classes.

    This parametrized test verifies that the sensor's availability property properly
    delegates to parent class implementations based on coordinator update status.

    Coverage target: sensor.py line 113 (availability property override)
    """
    # Set coordinator update status
    mock_coordinator_basic.last_update_success = last_update_success

    # Create sensor instance (entity description is created internally)
    sensor = LastMovementTimestampSensor(mock_coordinator_basic)

    # Test that availability property delegates to parent and reflects update status
    availability = sensor.available

    # Verify that the property delegation works and returns expected availability
    assert availability == expected_availability
    assert isinstance(availability, bool)


async def test_sensor_with_valid_coordinator_data_and_movement_history(mock_coordinator_basic) -> None:
    """Test timestamp sensor with valid coordinator data and movement history.

    This test ensures that when coordinator data is available AND there's movement
    history, the sensor returns a timestamp string.

    Complementary test to verify the positive case alongside the missing data tests.
    """
    from datetime import datetime, timezone

    # Set valid coordinator data
    mock_coordinator_basic.data = {
        "covers": {
            "cover.test": {
                "position": 50,
                COVER_ATTR_POS_TARGET_DESIRED: 75,
            }
        },
        "temp_current_max": 22.5,
    }
    mock_coordinator_basic.last_update_success = True

    # Add movement history
    now = datetime.now(timezone.utc)
    mock_coordinator_basic._cover_pos_history_mgr.add("cover.test", 50, cover_moved=True, timestamp=now)

    # Create sensor instance (entity description is created internally)
    sensor = LastMovementTimestampSensor(mock_coordinator_basic)

    # Verify sensor returns valid datetime when movement history exists
    native_value = sensor.native_value
    assert native_value is not None
    assert isinstance(native_value, datetime)
    assert native_value == now


async def test_sensor_with_invalid_covers_type(mock_coordinator_basic) -> None:
    """Test timestamp sensor handles non-dict covers data gracefully.

    This test ensures that when coordinator data has covers but it's not a dict
    (e.g., a string or list), the sensor handles it safely and returns None.

    Coverage target: sensor.py line 162 (isinstance check for covers)
    """
    # Set coordinator data with covers as a non-dict type
    mock_coordinator_basic.data = {
        "covers": "invalid_string_instead_of_dict",
    }
    mock_coordinator_basic.last_update_success = True

    # Create sensor instance
    sensor = LastMovementTimestampSensor(mock_coordinator_basic)

    # Verify sensor returns None when covers is not a dict
    native_value = sensor.native_value
    assert native_value is None
