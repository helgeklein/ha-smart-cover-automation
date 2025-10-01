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

from custom_components.smart_cover_automation.const import COVER_ATTR_POS_TARGET_DESIRED
from custom_components.smart_cover_automation.sensor import ENTITY_DESCRIPTIONS, AutomationStatusSensor


@pytest.mark.parametrize(
    "coordinator_data, last_update_success, expected_result_type",
    [
        ({}, True, type(None)),  # Empty data, successful update
        ({}, False, type(None)),  # Empty data, failed update
        (None, True, type(None)),  # None data, successful update
        (None, False, type(None)),  # None data, failed update
        ({"covers": {}}, True, str),  # Valid data structure, successful update
        ({"covers": {}}, False, str),  # Valid data structure, failed update
    ],
)
async def test_sensor_native_value_with_various_data_states(
    mock_coordinator_basic, coordinator_data, last_update_success, expected_result_type
) -> None:
    """Test sensor native value with various coordinator data states.

    This parametrized test verifies that the sensor handles different combinations
    of coordinator data availability and update success states appropriately.

    Coverage target: sensor.py line 125 (native_value with missing data)
    """
    # Set coordinator data and update status
    mock_coordinator_basic.data = coordinator_data
    mock_coordinator_basic.last_update_success = last_update_success

    # Create sensor instance with entity description
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(mock_coordinator_basic, entity_description)

    # Get native value
    native_value = sensor.native_value

    # Verify the result type matches expectations
    if expected_result_type is type(None):
        assert native_value is None
    else:
        assert isinstance(native_value, expected_result_type)


@pytest.mark.parametrize(
    "coordinator_data, last_update_success, expected_result_type",
    [
        ({}, True, type(None)),  # Empty data, successful update
        ({}, False, type(None)),  # Empty data, failed update
        (None, True, type(None)),  # None data, successful update
        (None, False, type(None)),  # None data, failed update
        ({"covers": {}}, True, dict),  # Valid data structure, successful update
        ({"covers": {}}, False, dict),  # Valid data structure, failed update
    ],
)
async def test_sensor_extra_state_attributes_with_various_data_states(
    mock_coordinator_basic, coordinator_data, last_update_success, expected_result_type
) -> None:
    """Test sensor extra state attributes with various coordinator data states.

    This parametrized test verifies that the sensor handles different combinations
    of coordinator data availability and update success states appropriately.

    Coverage target: sensor.py line 137 (extra_state_attributes with missing data)
    """
    # Set coordinator data and update status
    mock_coordinator_basic.data = coordinator_data
    mock_coordinator_basic.last_update_success = last_update_success

    # Create sensor instance with entity description
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(mock_coordinator_basic, entity_description)

    # Get extra state attributes
    extra_attributes = sensor.extra_state_attributes

    # Verify the result type matches expectations
    if expected_result_type is type(None):
        assert extra_attributes is None
    else:
        assert isinstance(extra_attributes, expected_result_type)


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

    # Create sensor instance
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(mock_coordinator_basic, entity_description)

    # Test that availability property delegates to parent and reflects update status
    availability = sensor.available

    # Verify that the property delegation works and returns expected availability
    assert availability == expected_availability
    assert isinstance(availability, bool)


async def test_sensor_with_valid_coordinator_data(mock_coordinator_basic) -> None:
    """Test sensor behavior with valid coordinator data.

    This test ensures that when coordinator data is available, the sensor
    properly processes and returns appropriate values.

    Complementary test to verify the positive case alongside the missing data tests.
    """
    # Set valid coordinator data
    mock_coordinator_basic.data = {
        "covers": {
            "cover.test": {
                "position": 50,
                COVER_ATTR_POS_TARGET_DESIRED: 75,
            }
        },
        "temp_current": 22.5,
    }
    mock_coordinator_basic.last_update_success = True

    # Create sensor instance with entity description
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    sensor = AutomationStatusSensor(mock_coordinator_basic, entity_description)

    # Verify sensor returns valid data when coordinator data is available
    native_value = sensor.native_value
    assert native_value is not None
    assert isinstance(native_value, str)

    extra_attributes = sensor.extra_state_attributes
    assert extra_attributes is not None
    assert isinstance(extra_attributes, dict)
