"""Tests for number platform setup.

This module tests the async_setup_entry function that creates and registers
all number entities when the integration is loaded.

Coverage target: number.py lines 31-54 (async_setup_entry function)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from custom_components.smart_cover_automation.number import (
    SunElevationThresholdNumber,
    TempThresholdNumber,
    async_setup_entry,
)

if TYPE_CHECKING:
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


async def test_async_setup_entry_creates_all_numbers(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that async_setup_entry creates all number entities.

    Verifies that the setup function creates instances of:
    - TempThresholdNumber

    Coverage target: number.py lines 31-54
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

    # Verify we have exactly 2 entities
    assert len(entities_list) == 2

    # Verify the entity types are correct
    assert isinstance(entities_list[0], SunElevationThresholdNumber)
    assert isinstance(entities_list[1], TempThresholdNumber)


async def test_async_setup_entry_entities_use_coordinator(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that all created numbers are properly linked to the coordinator.

    Verifies that each number entity receives and stores a reference to
    the coordinator, enabling them to read configuration and trigger updates.

    Coverage target: number.py lines 31-54
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


async def test_async_setup_entry_with_real_hass_instance(
    mock_hass_with_spec,
    mock_config_entry_basic,
) -> None:
    """Test async_setup_entry with a real-ish Home Assistant instance.

    This test uses a more realistic mock of Home Assistant to verify that
    the setup process works correctly with actual HA components.

    Coverage target: number.py lines 31-54
    """
    from typing import Iterable, cast

    from homeassistant.helpers.entity import Entity

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    # Setup the number platform
    await async_setup_entry(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Verify we got the expected entities
    assert len(captured) == 2
    assert isinstance(captured[0], SunElevationThresholdNumber)
    assert isinstance(captured[1], TempThresholdNumber)
