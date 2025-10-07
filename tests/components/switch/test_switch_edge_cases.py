"""Edge case tests for the switch platform.

This module tests specific edge cases and behavioral branches for the Smart Cover
Automation switch entity that require special test conditions or parameter variations.
"""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.switch import EnabledSwitch


@pytest.mark.parametrize(
    "last_update_success, expected_availability",
    [
        (True, True),  # Successful update should be available
        (False, False),  # Failed update should be unavailable
    ],
)
async def test_switch_availability_property_delegation(mock_coordinator_basic, last_update_success, expected_availability) -> None:
    """Test switch availability property delegation to parent classes.

    This parametrized test verifies that the switch's availability property properly
    delegates to parent class implementations based on coordinator update status.

    Coverage target: switch.py line 100 (availability property override)
    """
    # Set coordinator update status
    mock_coordinator_basic.last_update_success = last_update_success

    # Create enabled switch instance directly
    switch = EnabledSwitch(mock_coordinator_basic)

    # Test that availability property delegates to parent and reflects update status
    availability = switch.available

    # Verify that the property delegation works and returns expected availability
    assert availability == expected_availability
    assert isinstance(availability, bool)


@pytest.mark.parametrize(
    "enabled_config_value, expected_is_on",
    [
        (True, True),  # Enabled configuration should return True
        (False, False),  # Disabled configuration should return False
        (1, True),  # Truthy integer should return True
        (0, False),  # Falsy integer should return False
        ("true", True),  # String representation should be coerced to True (non-empty string)
        ("false", True),  # String representation should be coerced to True (non-empty string)
    ],
)
async def test_switch_is_on_property_with_config_resolution(
    mock_coordinator_basic, enabled_config_value: Any, expected_is_on: bool
) -> None:
    """Test switch is_on property with various configuration values.

    This parametrized test verifies that the switch's is_on property properly resolves
    different types of configuration values and returns the correct enabled state.

    Coverage target: switch.py line 110 (is_on property with resolve_entry call)
    """
    # Set the enabled configuration value
    mock_coordinator_basic.config_entry.data = {ConfKeys.ENABLED.value: enabled_config_value}
    mock_coordinator_basic.config_entry.options = {}

    # Create enabled switch instance directly
    switch = EnabledSwitch(mock_coordinator_basic)

    # Test that is_on property accesses resolved configuration
    is_on_state = switch.is_on

    # Verify that the property returns the expected configuration enabled state
    assert isinstance(is_on_state, bool)
    assert is_on_state == expected_is_on
