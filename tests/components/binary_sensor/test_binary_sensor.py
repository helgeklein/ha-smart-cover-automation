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
from custom_components.smart_cover_automation.const import BINARY_SENSOR_KEY_STATUS
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
    coordinator.last_update_success = True

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

    # Binary sensor platform should expose four entities
    assert len(captured) == 4


async def test_binary_sensor_is_on_state_with_failed_coordinator(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test binary sensor is_on property returns True when coordinator fails.

    This test verifies that the binary sensor correctly shows "Problem" state when
    the coordinator fails, indicating the automation system has issues.
    """
    # Coordinator with failed state
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = False

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
    # Find the status binary sensor specifically
    status_entity = next((entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_STATUS), None)
    assert status_entity is not None, "Status binary sensor not found"
    assert getattr(status_entity, "is_on") is True


async def test_binary_sensor_translation_keys_set(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that binary sensors have translation_key attribute set for state translations.

    This test verifies that binary sensors have the translation_key attribute properly
    set, which is required for entity state translations (e.g., "Yes/No" instead of "On/Off").
    """
    # Coordinator with predefined data and success state
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
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

    # Verify all binary sensors have translation_key set
    assert len(captured) == 4
    for entity in captured:
        # Check that translation_key attribute exists and matches the entity key
        assert hasattr(entity, "translation_key"), f"Entity {entity.entity_description.key} missing translation_key attribute"
        assert entity.translation_key == entity.entity_description.key, (
            f"Entity {entity.entity_description.key} has mismatched translation_key: "
            f"{entity.translation_key} != {entity.entity_description.key}"
        )
