"""Tests for LockModeSelect entity.

This module contains tests for the LockModeSelect entity, which provides
a UI control for users to change the lock mode of the automation system.

Coverage target: select.py lines 88-122 (LockModeSelect class)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.const import (
    SELECT_KEY_LOCK_MODE,
    LockMode,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.select import (
    LockModeSelect,
    async_setup_entry,
)

if TYPE_CHECKING:
    pass


async def test_lock_mode_select_entity_properties(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test LockModeSelect entity properties.

    Verifies that the LockModeSelect entity is properly initialized with:
    - Correct entity description
    - Proper translation key
    - Icon
    - Entity category
    - Options list from LockMode enum

    Coverage target: select.py lines 88-98
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    # Setup the select platform
    await async_setup_entry(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the lock mode select entity
    lock_mode_select = captured[0]
    assert isinstance(lock_mode_select, LockModeSelect)

    # Verify entity description properties
    assert lock_mode_select.entity_description.key == SELECT_KEY_LOCK_MODE
    assert lock_mode_select.entity_description.translation_key == SELECT_KEY_LOCK_MODE
    assert lock_mode_select.entity_description.icon == "mdi:lock"
    from homeassistant.const import EntityCategory

    assert lock_mode_select.entity_description.entity_category == EntityCategory.CONFIG

    # Verify unique_id format
    assert lock_mode_select.unique_id == f"{mock_config_entry_basic.entry_id}_{SELECT_KEY_LOCK_MODE}"

    # Verify options list contains all lock modes
    expected_options = [mode.value for mode in LockMode]
    assert lock_mode_select.options == expected_options
    assert LockMode.UNLOCKED.value in lock_mode_select.options
    assert LockMode.HOLD_POSITION.value in lock_mode_select.options
    assert LockMode.FORCE_OPEN.value in lock_mode_select.options
    assert LockMode.FORCE_CLOSE.value in lock_mode_select.options


async def test_lock_mode_select_current_option_returns_coordinator_lock_mode(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that current_option property returns the coordinator's lock mode.

    Verifies that the select entity correctly reads the current lock mode
    from the coordinator.

    Coverage target: select.py lines 100-106
    """
    from custom_components.smart_cover_automation.config import ConfKeys

    # Set lock mode in config entry options
    mock_config_entry_basic.options[ConfKeys.LOCK_MODE.value] = LockMode.FORCE_CLOSE.value

    # Create coordinator with specific lock mode
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create entity
    lock_mode_select = LockModeSelect(coordinator)

    # Verify current_option returns coordinator's lock_mode
    assert lock_mode_select.current_option == LockMode.FORCE_CLOSE.value


@pytest.mark.parametrize(
    "lock_mode",
    [LockMode.UNLOCKED, LockMode.HOLD_POSITION, LockMode.FORCE_OPEN, LockMode.FORCE_CLOSE],
)
async def test_lock_mode_select_current_option_all_modes(mock_hass_with_spec, mock_config_entry_basic, lock_mode: LockMode) -> None:
    """Test current_option for all valid lock modes.

    Parametrized test to verify that current_option correctly reflects
    all possible lock mode values.

    Coverage target: select.py lines 100-106
    """
    from custom_components.smart_cover_automation.config import ConfKeys

    # Set lock mode in config entry options
    mock_config_entry_basic.options[ConfKeys.LOCK_MODE.value] = lock_mode.value

    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    lock_mode_select = LockModeSelect(coordinator)

    assert lock_mode_select.current_option == lock_mode.value


async def test_lock_mode_select_async_select_option_valid(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test async_select_option with valid lock mode string.

    Verifies that selecting a valid lock mode option properly calls
    the coordinator's async_set_lock_mode method.

    Coverage target: select.py lines 108-122 (success path)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.async_set_lock_mode = AsyncMock()
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create entity
    lock_mode_select = LockModeSelect(coordinator)

    # Select a new lock mode
    await lock_mode_select.async_select_option(LockMode.FORCE_OPEN.value)

    # Verify coordinator method was called with correct enum value
    coordinator.async_set_lock_mode.assert_called_once_with(LockMode.FORCE_OPEN)


@pytest.mark.parametrize(
    "option",
    [LockMode.UNLOCKED.value, LockMode.HOLD_POSITION.value, LockMode.FORCE_OPEN.value, LockMode.FORCE_CLOSE.value],
)
async def test_lock_mode_select_async_select_option_all_valid_modes(mock_hass_with_spec, mock_config_entry_basic, option: str) -> None:
    """Test async_select_option with all valid lock mode strings.

    Parametrized test to verify that all valid lock mode strings are
    properly converted to enum values and passed to the coordinator.

    Coverage target: select.py lines 108-122 (success path)
    """
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.async_set_lock_mode = AsyncMock()
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    lock_mode_select = LockModeSelect(coordinator)

    # Select the lock mode
    await lock_mode_select.async_select_option(option)

    # Verify coordinator method was called with correct enum value
    expected_enum = LockMode(option)
    coordinator.async_set_lock_mode.assert_called_once_with(expected_enum)


async def test_lock_mode_select_async_select_option_invalid(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test async_select_option with invalid lock mode string.

    Verifies that selecting an invalid lock mode option:
    1. Logs an error
    2. Does not call the coordinator's async_set_lock_mode method
    3. Returns without raising an exception

    Coverage target: select.py lines 116-122 (error path)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.async_set_lock_mode = AsyncMock()
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Patch the Log class before entity creation (logger is instantiated in __init__)
    with patch("custom_components.smart_cover_automation.select.Log") as mock_log_class:
        mock_logger = MagicMock()
        mock_log_class.return_value = mock_logger

        # Create entity
        lock_mode_select = LockModeSelect(coordinator)

        # Try to select an invalid lock mode
        invalid_option = "invalid_lock_mode"
        await lock_mode_select.async_select_option(invalid_option)

        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_message = mock_logger.error.call_args[0][0]
        assert "Invalid lock mode value" in error_message
        assert invalid_option in error_message

        # Verify coordinator method was NOT called
        coordinator.async_set_lock_mode.assert_not_called()


async def test_lock_mode_select_async_select_option_empty_string(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test async_select_option with empty string.

    Verifies error handling for edge case input.

    Coverage target: select.py lines 116-122 (error path)
    """
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.async_set_lock_mode = AsyncMock()
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Patch the Log class before entity creation (logger is instantiated in __init__)
    with patch("custom_components.smart_cover_automation.select.Log") as mock_log_class:
        mock_logger = MagicMock()
        mock_log_class.return_value = mock_logger

        lock_mode_select = LockModeSelect(coordinator)

        await lock_mode_select.async_select_option("")

        # Should log error
        mock_logger.error.assert_called_once()
        # Should not call coordinator
        coordinator.async_set_lock_mode.assert_not_called()


async def test_lock_mode_select_async_select_option_none_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test async_select_option with None value.

    Verifies error handling when None is passed (though shouldn't happen in practice).

    Coverage target: select.py lines 116-122 (error path)
    """
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.async_set_lock_mode = AsyncMock()
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Patch the Log class before entity creation (logger is instantiated in __init__)
    with patch("custom_components.smart_cover_automation.select.Log") as mock_log_class:
        mock_logger = MagicMock()
        mock_log_class.return_value = mock_logger

        lock_mode_select = LockModeSelect(coordinator)

        # Try to select None (edge case)
        await lock_mode_select.async_select_option(None)  # type: ignore[arg-type]

        # Should log error
        mock_logger.error.assert_called_once()
        # Should not call coordinator
        coordinator.async_set_lock_mode.assert_not_called()


async def test_lock_mode_select_availability(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that LockModeSelect availability reflects coordinator state.

    Verifies that the select entity inherits availability from CoordinatorEntity,
    meaning it's unavailable when the coordinator has errors.

    Coverage target: Verify entity inheritance behavior
    """
    # Create coordinator with failed state
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = False
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    # Setup the select platform
    await async_setup_entry(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    lock_mode_select = captured[0]

    # Verify entity is unavailable when coordinator fails
    assert lock_mode_select.available is False

    # Set coordinator to success state
    coordinator.last_update_success = True

    # Verify entity becomes available
    assert lock_mode_select.available is True


async def test_lock_mode_select_translation_key_set(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that LockModeSelect has translation_key set for localization.

    Verifies that the select entity has the translation_key attribute properly
    set, which is required for entity localization support.

    Coverage target: Verify entity description configuration
    """
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    lock_mode_select = LockModeSelect(coordinator)

    # Verify translation_key is set
    assert hasattr(lock_mode_select.entity_description, "translation_key")
    assert lock_mode_select.entity_description.translation_key == SELECT_KEY_LOCK_MODE


async def test_lock_mode_select_state_persistence(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that lock mode changes persist through coordinator state.

    Verifies that when the user changes the lock mode through the select entity,
    the change is reflected in subsequent current_option reads.

    Coverage target: Integration test for full change cycle
    """
    from custom_components.smart_cover_automation.config import ConfKeys

    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create a side effect that updates the config entry options to simulate real behavior
    def update_lock_mode(mode: LockMode) -> None:
        mock_config_entry_basic.options[ConfKeys.LOCK_MODE.value] = mode.value

    coordinator.async_set_lock_mode = AsyncMock(side_effect=update_lock_mode)
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    lock_mode_select = LockModeSelect(coordinator)

    # Initial state
    assert lock_mode_select.current_option == LockMode.UNLOCKED.value

    # Change to FORCE_CLOSE
    await lock_mode_select.async_select_option(LockMode.FORCE_CLOSE.value)

    # Verify state changed
    assert lock_mode_select.current_option == LockMode.FORCE_CLOSE.value

    # Change to HOLD_POSITION
    await lock_mode_select.async_select_option(LockMode.HOLD_POSITION.value)

    # Verify state changed again
    assert lock_mode_select.current_option == LockMode.HOLD_POSITION.value
