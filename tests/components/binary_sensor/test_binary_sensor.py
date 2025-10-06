"""Tests for binary sensor platform.

This module contains tests for the Smart Cover Automation integration's
binary sensor platform, which provides automation status indicators.
"""

from __future__ import annotations

from typing import Iterable, cast

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


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

    # Verify the binary sensor has the correct is_on state based on coordinator success
    # With PROBLEM device class: is_on=False when coordinator is working (no problems)
    assert getattr(entity, "is_on") is False


async def test_binary_sensor_is_on_state_with_failed_coordinator(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test binary sensor is_on property returns True when coordinator fails.

    This test verifies that the binary sensor correctly shows "Problem" state when
    the coordinator fails, indicating the automation system has issues.
    """
    # Coordinator with failed state
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = False  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data as HA would do during integration setup
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Verify binary sensor shows "Problem" (is_on=True) when coordinator fails
    entity = captured[0]
    assert getattr(entity, "is_on") is True
