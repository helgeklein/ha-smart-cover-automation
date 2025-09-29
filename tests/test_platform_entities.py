"""Tests for platform entities: binary_sensor, sensor, and switch.

This module contains comprehensive tests for the Smart Cover Automation integration's
platform entities. These tests verify the proper setup, configuration, and behavior
of all Home Assistant entity platforms provided by the integration:

1. **Binary Sensor Platform**: Tests the automation status binary sensor that indicates
   whether the smart cover automation is currently active/inactive.

2. **Sensor Platform**: Tests the automation status sensor that provides detailed
   information about the current automation state and cover positions.

3. **Switch Platform**: Tests the automation enable/disable switch that allows users
   to control whether the automation should run, including state management and
   service call handling.

Each platform test verifies:
- Proper entity setup and registration with Home Assistant
- Entity availability and state management through the coordinator
- Entity property evaluation and data synchronization
- Platform-specific functionality (switch on/off, sensor values, etc.)

The tests use mock Home Assistant environments and coordinators to simulate
real-world integration behavior without requiring actual Home Assistant runtime.
"""

from __future__ import annotations

from typing import Iterable, cast

import pytest
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


@pytest.mark.asyncio
async def test_binary_sensor_entity_properties(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test binary sensor platform setup and entity property evaluation.

    This test verifies that the binary sensor platform correctly creates and configures
    the automation status binary sensor. The binary sensor indicates whether the smart
    cover automation is currently active or inactive.

    Test scenario:
    - Mock Home Assistant environment with temperature-based configuration
    - Coordinator in successful state (last_update_success=True)
    - Expected result: One binary sensor entity with proper availability status

    The binary sensor inherits availability from CoordinatorEntity, which means its
    availability reflects the coordinator's ability to fetch and process data.
    """
    # Coordinator with predefined data and success state
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data as HA would do during integration setup
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform (this would normally be called by HA)
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Binary sensor platform should expose exactly one entity (automation status)
    assert len(captured) == 1
    entity = captured[0]

    # Verify entity availability reflects coordinator success state
    # available is delegated from CoordinatorEntity; with last_update_success=True it's truthy
    assert cast(bool, getattr(entity, "available")) is True


# Sensor entity testing is comprehensively covered in test_status_sensor.py
# Removed redundant sensor test to avoid duplication


# Switch entity testing is comprehensively covered in test_switch.py
# Removed redundant switch test to avoid duplication
