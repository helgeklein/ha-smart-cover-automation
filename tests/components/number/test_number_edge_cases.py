"""Edge case tests for number entities.

This module contains tests for edge cases and boundary conditions in the number
entities. These tests ensure robust behavior in unusual situations and verify
that the number entities handle edge cases gracefully.
"""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.number import TempThresholdNumber
from custom_components.smart_cover_automation.number import (
    async_setup_entry as async_setup_entry_number,
)


@pytest.mark.parametrize(
    ("test_value", "expected_valid"),
    [
        (10.0, True),  # Minimum value
        (40.0, True),  # Maximum value
        (25.0, True),  # Middle value
        (10.5, True),  # Just above minimum
        (39.5, True),  # Just below maximum
        (15.5, True),  # Valid half-step value
    ],
)
async def test_temp_threshold_valid_values(
    mock_coordinator_basic,
    test_value: float,
    expected_valid: bool,  # noqa: ARG001
) -> None:
    """Test that the temperature threshold accepts valid values within range.

    This test verifies that the number entity correctly accepts all valid
    values within its configured range (10.0 - 40.0°C) and with the
    correct step size (0.5°C).
    """
    # Setup integration
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = 25.0

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()  # type: ignore[attr-defined]

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Set the test value - should not raise an exception for valid values
    await temp_threshold.async_set_native_value(test_value)

    # Verify that the value was persisted
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.TEMP_THRESHOLD.value] == test_value


async def test_temp_threshold_number_entity_unique_id(mock_coordinator_basic) -> None:
    """Test that the temperature threshold number has a proper unique ID.

    This test verifies that the number entity has a unique ID that:
    - Includes the domain identifier
    - Includes the entity type identifier
    - Is stable across restarts
    """
    # Setup integration
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = 25.0

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Verify unique ID exists and has expected format
    assert temp_threshold.unique_id is not None
    assert "smart_cover_automation" in temp_threshold.unique_id
    assert "temp_threshold" in temp_threshold.unique_id


async def test_temp_threshold_multiple_updates(mock_coordinator_basic) -> None:
    """Test that the temperature threshold handles multiple rapid updates correctly.

    This test verifies that the number entity can handle multiple consecutive
    value changes without issues, ensuring that each update is properly persisted.
    """
    # Setup integration
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = 25.0

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()  # type: ignore[attr-defined]

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Perform multiple updates and update the runtime config to simulate the update listener
    values = [20.0, 25.5, 30.0, 35.5]
    for value in values:
        await temp_threshold.async_set_native_value(value)
        # Simulate the update listener updating the runtime config
        entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = value

    # Verify that the final value is correct
    assert temp_threshold.native_value == values[-1]

    # Verify that async_update_entry was called for each update
    assert mock_coordinator_basic.hass.config_entries.async_update_entry.call_count == len(values)


async def test_temp_threshold_zero_step_handling(mock_coordinator_basic) -> None:
    """Test that the temperature threshold properly defines a non-zero step.

    This test ensures that the number entity has a proper step value defined,
    which is required for Home Assistant to correctly display and validate
    the number input.
    """
    # Setup integration
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = 25.0

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Verify that step is a positive non-zero value
    assert temp_threshold.native_step is not None
    assert temp_threshold.native_step > 0
    assert temp_threshold.native_step == 0.5
