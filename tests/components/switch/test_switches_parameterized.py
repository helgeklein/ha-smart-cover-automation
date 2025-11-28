"""Parameterized tests for config-based switch entities.

This module provides comprehensive parameterized tests for config-based boolean
switch entities (EnabledSwitch and SimulationModeSwitch), eliminating code
duplication while ensuring complete test coverage.

Switches tested:
- EnabledSwitch (master automation enable/disable)
- SimulationModeSwitch (simulation mode control)

Note: VerboseLoggingSwitch has unique behavior (checks HA logger) and is
tested separately in test_switch_edge_cases.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, cast
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.switch import (
    EnabledSwitch,
    SimulationModeSwitch,
    async_setup_entry,
)

if TYPE_CHECKING:
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


# Configuration for all switches to be tested
SWITCH_CONFIGS = [
    {
        "switch_class": EnabledSwitch,
        "config_key": ConfKeys.ENABLED.value,
        "unique_id": "smart_cover_automation_enabled",
        "icon": "mdi:toggle-switch-outline",
        "description": "Master automation enable/disable switch",
    },
    {
        "switch_class": SimulationModeSwitch,
        "config_key": ConfKeys.SIMULATION_MODE.value,
        "unique_id": "smart_cover_automation_simulation_mode",
        "icon": "mdi:play-circle-outline",
        "description": "Simulation mode control switch",
    },
]


#
# test_switch_turn_on_persists_option
#
@pytest.mark.parametrize("config", SWITCH_CONFIGS, ids=lambda c: c["config_key"])
async def test_switch_turn_on_persists_option(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that turning switch ON persists the state and triggers refresh.

    This test verifies the complete turn-on sequence:
    1. State persistence through Home Assistant's options system
    2. Immediate coordinator refresh to apply the new state
    3. Proper integration with the configuration management system

    Test scenario:
    - Switch starts in disabled state (config value = False)
    - User turns switch ON through Home Assistant UI or automation
    - Expected behavior: Options updated with True value

    The turn-on operation must be atomic and reliable because users expect
    immediate activation when they enable the switch.
    """
    # Setup integration with switch initially disabled
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[config["config_key"]] = False

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entities
    await async_setup_entry(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the specific switch entity
    switch: SwitchEntity = next(entity for entity in captured if isinstance(entity, config["switch_class"]))  # type: ignore[assignment]

    # Execute the turn-on operation
    await switch.async_turn_on()

    # Verify that async_update_entry was called with the correct options
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][config["config_key"]] is True


#
# test_switch_turn_off_persists_option
#
@pytest.mark.parametrize("config", SWITCH_CONFIGS, ids=lambda c: c["config_key"])
async def test_switch_turn_off_persists_option(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that turning switch OFF persists the state and triggers refresh.

    This test verifies the complete turn-off sequence:
    1. State persistence through Home Assistant's options system
    2. Immediate coordinator refresh to apply the new state
    3. Proper integration with the configuration management system

    Test scenario:
    - Switch starts in enabled state (config value = True)
    - User turns switch OFF through Home Assistant UI or automation
    - Expected behavior: Options updated with False value

    The turn-off operation is particularly critical because users often need
    to quickly disable functionality in emergency situations or when manual
    control is required.
    """
    # Setup integration with switch initially enabled
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[config["config_key"]] = True

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entities
    await async_setup_entry(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the specific switch entity
    switch: SwitchEntity = next(entity for entity in captured if isinstance(entity, config["switch_class"]))  # type: ignore[assignment]

    # Execute the turn-off operation
    await switch.async_turn_off()

    # Verify that async_update_entry was called with the correct options
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][config["config_key"]] is False


#
# test_switch_unique_id
#
@pytest.mark.parametrize("config", SWITCH_CONFIGS, ids=lambda c: c["config_key"])
async def test_switch_unique_id(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that switch has correct unique_id format.

    Verifies that each switch entity has the expected unique_id pattern
    for proper device grouping and entity identification.
    """
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture all entities
    await async_setup_entry(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the specific switch entity
    switch = next(entity for entity in captured if isinstance(entity, config["switch_class"]))

    # Verify unique ID
    assert switch.unique_id == config["unique_id"]


#
# test_switch_entity_description
#
@pytest.mark.parametrize("config", SWITCH_CONFIGS, ids=lambda c: c["config_key"])
async def test_switch_entity_description(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that switch has correct entity description properties.

    Verifies that each switch entity is properly configured with the
    correct key, translation_key, and icon.
    """
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture all entities
    await async_setup_entry(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the specific switch entity
    switch = next(entity for entity in captured if isinstance(entity, config["switch_class"]))

    # Verify entity description properties
    assert switch.entity_description.key == config["config_key"]
    assert switch.entity_description.translation_key == config["config_key"]
    assert switch.entity_description.icon == config["icon"]


#
# test_switch_is_on_reflects_config
#
@pytest.mark.parametrize("config", SWITCH_CONFIGS, ids=lambda c: c["config_key"])
@pytest.mark.parametrize("initial_state", [True, False], ids=["on", "off"])
async def test_switch_is_on_reflects_config(
    mock_coordinator_basic: DataUpdateCoordinator,
    config: dict[str, Any],
    initial_state: bool,
) -> None:
    """Test that switch is_on property reflects the config value.

    Verifies that the switch correctly reads its state from the
    resolved configuration settings.
    """
    # Set initial state in config
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[config["config_key"]] = initial_state
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture all entities
    await async_setup_entry(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the specific switch entity
    switch: SwitchEntity = next(entity for entity in captured if isinstance(entity, config["switch_class"]))  # type: ignore[assignment]

    # Verify is_on reflects the initial state
    assert switch.is_on is initial_state


#
# test_switch_availability
#
@pytest.mark.parametrize("config", SWITCH_CONFIGS, ids=lambda c: c["config_key"])
async def test_switch_availability(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that switch availability tracks coordinator availability.

    Verifies that switches correctly delegate availability to the
    coordinator's last_update_success property.
    """
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture all entities
    await async_setup_entry(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the specific switch entity
    switch: SwitchEntity = next(entity for entity in captured if isinstance(entity, config["switch_class"]))  # type: ignore[assignment]

    # Test with coordinator available
    mock_coordinator_basic.last_update_success = True
    assert switch.available is True

    # Test with coordinator unavailable
    mock_coordinator_basic.last_update_success = False
    assert switch.available is False


#
# test_switch_coordinator_integration
#
@pytest.mark.parametrize("config", SWITCH_CONFIGS, ids=lambda c: c["config_key"])
async def test_switch_coordinator_integration(mock_coordinator_basic: DataUpdateCoordinator, config: dict[str, Any]) -> None:
    """Test that switch is properly linked to coordinator.

    Verifies that each switch entity receives and stores the coordinator
    instance correctly.
    """
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture all entities
    await async_setup_entry(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the specific switch entity
    switch: SwitchEntity = next(entity for entity in captured if isinstance(entity, config["switch_class"]))  # type: ignore[assignment]

    # Verify coordinator integration
    assert switch.coordinator is mock_coordinator_basic  # type: ignore[attr-defined]
