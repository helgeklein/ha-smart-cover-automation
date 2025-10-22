"""Tests for sensor platform setup.

This module tests the async_setup_entry function that creates and registers
all sensor entities when the integration is loaded.

Coverage target: sensor.py lines 50-60 (async_setup_entry function)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from custom_components.smart_cover_automation.sensor import (
    AutomationDisabledTimeRangeSensor,
    SunAzimuthSensor,
    SunElevationSensor,
    TempCurrentMaxSensor,
    TempThresholdSensor,
    async_setup_entry,
)

if TYPE_CHECKING:
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


async def test_async_setup_entry_creates_all_sensors(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that async_setup_entry creates all sensor entities.

    Verifies that the setup function creates instances of:
    - AutomationDisabledTimeRangeSensor
    - SunAzimuthSensor
    - SunElevationSensor
    - TempCurrentMaxSensor
    - TempThresholdSensor

    Coverage target: sensor.py lines 50-60
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

    # Verify we have exactly 5 entities
    assert len(entities_list) == 5

    # Verify each entity type is present
    entity_types = [type(entity) for entity in entities_list]
    assert AutomationDisabledTimeRangeSensor in entity_types
    assert SunAzimuthSensor in entity_types
    assert SunElevationSensor in entity_types
    assert TempCurrentMaxSensor in entity_types
    assert TempThresholdSensor in entity_types


async def test_async_setup_entry_entities_use_coordinator(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that all created sensors are properly linked to the coordinator.

    Verifies that each sensor entity receives the coordinator instance from
    the config entry's runtime data.

    Coverage target: sensor.py lines 50-60
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

    # Verify each entity has the coordinator
    for entity in entities_list:
        assert entity.coordinator is mock_coordinator_basic


async def test_async_setup_entry_with_real_hass_instance() -> None:
    """Test async_setup_entry integration with a more realistic setup.

    This test verifies the setup process works with more realistic mock objects
    that simulate the actual Home Assistant environment.

    Coverage target: sensor.py lines 50-60
    """
    # Create a realistic mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "sun_azimuth": 180.0,
        "sun_elevation": 45.0,
        "temp_current_max": 25.0,
        "temp_threshold": 22.0,
        "covers": {},
    }

    # Create mock config entry
    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.coordinator = mock_coordinator

    # Track entities that were added
    added_entities = []

    def capture_entities(new_entities, update_before_add=False):  # noqa: ARG001 Unused function argument
        added_entities.extend(new_entities)

    # Call async_setup_entry
    await async_setup_entry(
        hass=MagicMock(),
        entry=mock_entry,
        async_add_entities=capture_entities,
    )

    # Verify we captured 5 entities
    assert len(added_entities) == 5

    # Verify entities are the correct types
    assert any(isinstance(e, AutomationDisabledTimeRangeSensor) for e in added_entities)
    assert any(isinstance(e, SunAzimuthSensor) for e in added_entities)
    assert any(isinstance(e, SunElevationSensor) for e in added_entities)
    assert any(isinstance(e, TempCurrentMaxSensor) for e in added_entities)
    assert any(isinstance(e, TempThresholdSensor) for e in added_entities)
