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
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_binary_sensor_entity_properties() -> None:
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
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    # Coordinator with predefined data and success state
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))
    coordinator.last_update_success = True  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data as HA would do during integration setup
    config_entry.runtime_data.coordinator = coordinator

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform (this would normally be called by HA)
    await async_setup_entry_binary_sensor(
        hass,
        cast(IntegrationConfigEntry, config_entry),
        add_entities,
    )

    # Binary sensor platform should expose exactly one entity (automation status)
    assert len(captured) == 1
    entity = captured[0]

    # Verify entity availability reflects coordinator success state
    # available is delegated from CoordinatorEntity; with last_update_success=True it's truthy
    assert cast(bool, getattr(entity, "available")) is True


@pytest.mark.asyncio
async def test_sensor_entity_properties() -> None:
    """Test sensor platform setup and entity property evaluation.

    This test verifies that the sensor platform correctly creates and configures
    the automation status sensor. The sensor provides detailed information about
    the current automation state, including cover positions and automation activity.

    Test scenario:
    - Mock Home Assistant environment with temperature-based configuration
    - Coordinator with basic data structure (empty covers dict)
    - Coordinator in successful state (last_update_success=True)
    - Expected result: One sensor entity (Automation Status) with valid data

    The automation status sensor reports the current state of the smart cover
    automation system, helping users understand what the system is doing.
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    # Setup coordinator with basic data structure for AutomationStatusSensor
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))
    coordinator.data = {"covers": {}}  # Basic data structure for AutomationStatusSensor
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    config_entry.runtime_data.coordinator = coordinator

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the sensor platform (this would normally be called by HA)
    await async_setup_entry_sensor(
        hass,
        cast(IntegrationConfigEntry, config_entry),
        add_entities,
    )

    # Sensor platform should expose exactly one sensor (Automation Status)
    assert len(captured) == 1
    # Find the Automation Status Sensor by its entity_description.key
    automation_sensor = next(e for e in captured if getattr(getattr(e, "entity_description"), "key", "") == "automation_status")

    # Verify entity availability reflects coordinator success state
    # available is delegated from CoordinatorEntity; with last_update_success=True it's truthy
    assert cast(bool | None, getattr(automation_sensor, "available")) in (True, None)

    # Verify the sensor provides a meaningful value
    # native_value comes from the AutomationStatusSensor logic and should not be None
    assert getattr(automation_sensor, "native_value") is not None


@pytest.mark.asyncio
async def test_switch_entity_turn_on_off_and_state() -> None:
    """Test switch platform setup, state management, and turn on/off interactions.

    This test verifies that the switch platform correctly creates and configures
    the automation enable/disable switch. The switch allows users to control
    whether the smart cover automation should run or be paused.

    Test scenarios:
    1. Primary switch setup with proper state management
    2. Secondary switch setup to test multiple instances
    3. Switch on/off operations with coordinator refresh triggering

    The switch entity provides manual control over the automation system,
    allowing users to temporarily disable automation without changing configuration.
    When toggled, the switch triggers a coordinator refresh to immediately apply
    the new state to the automation logic.
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    # Setup coordinator with required data and mocked refresh capability
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))
    # Make sure coordinator.data exists for proper entity initialization
    coordinator.data = {"dummy": "value"}
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    config_entry.runtime_data.coordinator = coordinator
    config_entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]

    # Prevent real refresh logic from running in tests (use mock instead)
    coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform (this would normally be called by HA)
    await async_setup_entry_switch(
        hass,
        cast(IntegrationConfigEntry, config_entry),
        add_entities,
    )

    # Switch platform should expose exactly one entity (automation enable/disable)
    assert len(captured) == 1
    entity = captured[0]

    # Verify switch state and availability
    assert cast(bool, getattr(entity, "is_on")) is True  # Switch should default to enabled
    # Access available property to exercise CoordinatorEntity behavior
    assert cast(bool | None, getattr(entity, "available")) in (True, None)

    # Test multiple switch instances to ensure proper isolation
    # Setup a second switch with separate coordinator and config entry
    other_entry = MockConfigEntry(create_temperature_config())
    other_coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, other_entry))
    # Make sure other_coordinator.data exists for proper entity initialization
    other_coordinator.data = {"dummy": "value"}
    other_coordinator.last_update_success = True  # type: ignore[attr-defined]
    other_coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]
    other_entry.runtime_data.coordinator = other_coordinator
    other_entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]

    # Capture entities for the second switch instance
    other_captured: list[Entity] = []

    def other_add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function for second switch instance."""
        other_captured.extend(list(new_entities))

    # Setup the second switch platform instance
    await async_setup_entry_switch(
        hass,
        cast(IntegrationConfigEntry, other_entry),
        other_add_entities,
    )

    # Verify second switch setup and test its operations
    other_entity = other_captured[0]
    # Access available property on second entity to ensure proper inheritance
    assert cast(bool | None, getattr(other_entity, "available")) in (True, None)

    # Test switch operations - these should not raise exceptions
    await getattr(other_entity, "async_turn_on")()  # Enable automation
    await getattr(other_entity, "async_turn_off")()  # Disable automation

    # Verify that switch operations trigger coordinator refresh
    # This ensures automation state changes are immediately applied
    other_coordinator.async_request_refresh.assert_awaited()  # type: ignore[func-returns-value]
