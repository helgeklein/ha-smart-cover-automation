"""Tests for select platform setup.

This module tests the async_setup_entry function that creates and registers
all select entities when the integration is loaded.

Coverage target: select.py lines 28-42 (async_setup_entry function)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from custom_components.smart_cover_automation.select import (
    LockModeSelect,
    async_setup_entry,
)

if TYPE_CHECKING:
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


async def test_async_setup_entry_creates_all_selects(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that async_setup_entry creates all select entities.

    Verifies that the setup function creates instances of:
    - LockModeSelect

    Coverage target: select.py lines 28-42
    """
    # Create mock config entry with runtime data
    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.coordinator = mock_coordinator_basic

    # Create mock async_add_entities callback
    mock_add_entities = MagicMock()

    # Call async_setup_entry
    await async_setup_entry(
        hass=MagicMock(),  # hass is unused but required by interface
        entry=mock_entry,
        async_add_entities=mock_add_entities,
    )

    # Verify async_add_entities was called
    mock_add_entities.assert_called_once()

    # Get the list of entities that were passed to async_add_entities
    entities_list = mock_add_entities.call_args[0][0]

    # Verify we have exactly 1 entity
    assert len(entities_list) == 1

    # Verify the entity type is correct
    assert isinstance(entities_list[0], LockModeSelect)


async def test_async_setup_entry_entities_use_coordinator(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that all created selects are properly linked to the coordinator.

    Verifies that each select entity receives the coordinator instance from
    the config entry's runtime data.

    Coverage target: select.py lines 28-42
    """
    # Create mock config entry with runtime data
    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.coordinator = mock_coordinator_basic

    # Create mock async_add_entities callback
    mock_add_entities = MagicMock()

    # Call async_setup_entry
    await async_setup_entry(
        hass=MagicMock(),
        entry=mock_entry,
        async_add_entities=mock_add_entities,
    )

    # Get the list of entities
    entities_list = mock_add_entities.call_args[0][0]

    # Verify all entities have the coordinator
    for entity in entities_list:
        assert entity.coordinator is mock_coordinator_basic


async def test_async_setup_entry_with_real_hass_instance(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test async_setup_entry with a real HomeAssistant instance.

    This test verifies that the select platform setup works correctly with
    a real (mocked) HomeAssistant instance, simulating actual integration setup.

    Coverage target: select.py lines 28-42
    """
    from typing import Iterable, cast

    from homeassistant.helpers.entity import Entity

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    # Create coordinator with real hass instance
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the select platform
    await async_setup_entry(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Should have exactly 1 select entity
    assert len(captured) == 1

    # Verify the entity is LockModeSelect
    assert isinstance(captured[0], LockModeSelect)

    # Verify entity has proper coordinator reference
    assert captured[0].coordinator is coordinator
