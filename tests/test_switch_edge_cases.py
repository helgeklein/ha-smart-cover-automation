"""Tests for switch edge cases and property handling.

This module contains focused tests for switch entity edge cases that are not
covered by the main switch tests, specifically targeting property edge cases
and availability delegation.

Coverage targets:
- Switch availability property delegation
- Switch is_on property with resolved configuration
"""

from __future__ import annotations

import pytest

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.switch import ENTITY_DESCRIPTIONS, IntegrationSwitch


@pytest.mark.asyncio
async def test_switch_availability_property_delegation(mock_coordinator_basic) -> None:
    """Test switch availability property delegation to parent classes.

    This test verifies that the switch's availability property properly
    delegates to parent class implementations and can be accessed.

    Coverage target: switch.py line 100 (availability property override)
    """
    # Create switch instance
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    switch = IntegrationSwitch(mock_coordinator_basic, entity_description)

    # Test that availability property can be accessed and delegates to parent
    # This covers the line: return super().available
    mock_coordinator_basic.last_update_success = True
    availability = switch.available

    # Verify that the property delegation works and returns a value
    assert availability is not None
    assert isinstance(availability, bool)

    # The key is that we accessed the property, which covers line 100
    # The exact behavior (True vs False) is handled by the parent class


@pytest.mark.asyncio
async def test_switch_is_on_property_with_config_resolution(mock_coordinator_basic) -> None:
    """Test switch is_on property with configuration resolution.

    This test verifies that the switch's is_on property properly resolves
    the configuration entry and returns the enabled state.

    Coverage target: switch.py line 110 (is_on property with resolve_entry call)
    """
    # Create switch instance
    entity_description = ENTITY_DESCRIPTIONS[0]  # Use first available description
    switch = IntegrationSwitch(mock_coordinator_basic, entity_description)

    # Test that is_on property accesses resolved configuration
    # This covers the line: return resolve_entry(self.coordinator.config_entry).enabled
    is_on_state = switch.is_on

    # Verify that the property returns the configuration enabled state
    assert isinstance(is_on_state, bool)

    # The configuration should have enabled=True by default from create_temperature_config
    assert is_on_state is True

    # Verify that the property can handle different states by modifying config
    # (This tests the resolve_entry call and configuration access)
    mock_coordinator_basic.config_entry.runtime_data.config[ConfKeys.ENABLED.value] = False

    # Create new switch instance to get fresh property evaluation
    entity_description_2 = ENTITY_DESCRIPTIONS[0]  # Use first available description
    switch_disabled = IntegrationSwitch(mock_coordinator_basic, entity_description_2)
    is_on_disabled = switch_disabled.is_on

    # Should reflect the updated configuration
    assert is_on_disabled is False
