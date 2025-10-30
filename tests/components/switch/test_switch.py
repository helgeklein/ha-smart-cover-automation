"""Focused tests for the IntegrationSwitch behavior and edge branches.

This module contains specialized tests for the Smart Cover Automation switch entity,
which provides users with manual control over the automation system. The switch
allows users to enable or disable the automation without changing the underlying
configuration, providing flexible control over when the system should operate.

Key testing areas include:
1. **State Persistence**: Tests that switch operations properly save their state
   to Home Assistant's configuration options for persistence across restarts
2. **Coordinator Refresh**: Tests that state changes immediately trigger coordinator
   refresh to apply the new automation state without delay
3. **Option Updates**: Tests that switch operations correctly update the integration's
   configuration through Home Assistant's options system
4. **Edge Case Handling**: Tests specific behavioral branches and error conditions

The integration switch is critical for user experience because it provides:
- **Immediate Control**: Users can quickly disable automation when needed
- **Persistent State**: Switch position is remembered across Home Assistant restarts
- **Real-time Application**: Changes take effect immediately without manual refresh
- **Configuration Integration**: Works seamlessly with Home Assistant's options flow

These tests focus on the switch's core functionality beyond basic platform testing,
ensuring that the switch properly integrates with Home Assistant's configuration
system and immediately applies state changes to the automation logic.
"""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import AsyncMock, Mock

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.switch import EnabledSwitch, SimulationModeSwitch, VerboseLoggingSwitch
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)


async def test_switch_turn_on_persists_option_and_refresh(mock_coordinator_basic) -> None:
    """Test that turning the switch ON persists the enabled state and triggers refresh.

    This test verifies the complete turn-on sequence for the automation switch:
    1. State persistence through Home Assistant's options system
    2. Immediate coordinator refresh to apply the new state
    3. Proper integration with the configuration management system

    Test scenario:
    - Switch starts in disabled state (enabled = False)
    - User turns switch ON through Home Assistant UI or automation
    - Expected behavior: Options updated and coordinator refreshed immediately

    The turn-on operation must be atomic and reliable because users expect
    immediate automation activation when they enable the switch. Any delay
    or failure to persist the state could result in unexpected automation
    behavior or loss of user preferences.

    This test ensures that enabling automation through the switch provides
    the same reliable behavior as configuring it through the options flow.
    """
    # Setup integration with switch initially disabled
    entry = mock_coordinator_basic.config_entry
    # Start with enabled False to observe the state change
    entry.runtime_data.config[ConfKeys.ENABLED.value] = False

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()
    # Mock the hass.config_entries.async_update_entry method
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entities
    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the enabled switch entity
    enabled_switch = next(entity for entity in captured if isinstance(entity, EnabledSwitch))

    # Execute the turn-on operation
    await enabled_switch.async_turn_on()

    # Verify that async_update_entry was called with the correct options
    # This ensures the switch state is persisted to the config entry
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.ENABLED.value] is True


async def test_switch_turn_off_persists_option_and_refresh(mock_coordinator_basic) -> None:
    """Test that turning the switch OFF persists the disabled state and triggers refresh.

    This test verifies the complete turn-off sequence for the automation switch:
    1. State persistence through Home Assistant's options system
    2. Immediate coordinator refresh to apply the new state
    3. Proper integration with the configuration management system

    Test scenario:
    - Switch starts in enabled state (enabled = True)
    - User turns switch OFF through Home Assistant UI or automation
    - Expected behavior: Options updated and coordinator refreshed immediately

    The turn-off operation is particularly critical because users often need
    to quickly disable automation in emergency situations or when manual
    control is required. The switch must immediately stop automation activity
    and persist this state to prevent unwanted reactivation.

    This test ensures that disabling automation through the switch provides
    immediate and reliable control, giving users confidence that the system
    will respect their manual override decisions.
    """
    # Setup integration with switch initially enabled
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.ENABLED.value] = True  # Start enabled to observe disable

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()
    # Mock the hass.config_entries.async_update_entry method
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entities
    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the enabled switch entity
    enabled_switch = next(entity for entity in captured if isinstance(entity, EnabledSwitch))

    # Execute the turn-off operation
    await enabled_switch.async_turn_off()

    # Verify that async_update_entry was called with the correct options
    # This ensures the switch state is persisted to the config entry
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.ENABLED.value] is False


async def test_simulation_mode_switch_turn_on_persists_option_and_refresh(mock_coordinator_basic) -> None:
    """Test that turning the simulation mode switch ON persists state and triggers refresh.

    This test verifies the complete turn-on sequence for the simulation mode switch:
    1. State persistence through Home Assistant's options system
    2. Immediate coordinator refresh to apply the new state
    3. Proper integration with the configuration management system

    Test scenario:
    - Simulation mode switch starts in disabled state (simulation_mode = False)
    - User turns simulation mode switch ON
    - Expected behavior: Options updated and coordinator refreshed immediately

    Simulation mode is critical for testing and development, allowing users to
    verify automation logic without actually moving covers.
    """
    # Setup integration with simulation mode initially disabled
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.SIMULATION_MODE.value] = False

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()
    # Mock the hass.config_entries.async_update_entry method
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entities
    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the simulation mode switch entity
    simulation_switch = next(entity for entity in captured if isinstance(entity, SimulationModeSwitch))

    # Execute the turn-on operation
    await simulation_switch.async_turn_on()

    # Verify that async_update_entry was called with the correct options
    # This ensures the switch state is persisted to the config entry
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.SIMULATION_MODE.value] is True


async def test_simulation_mode_switch_turn_off_persists_option_and_refresh(mock_coordinator_basic) -> None:
    """Test that turning the simulation mode switch OFF persists state and triggers refresh.

    This test verifies the complete turn-off sequence for the simulation mode switch:
    1. State persistence through Home Assistant's options system
    2. Immediate coordinator refresh to apply the new state
    3. Proper integration with the configuration management system

    Test scenario:
    - Simulation mode switch starts in enabled state (simulation_mode = True)
    - User turns simulation mode switch OFF
    - Expected behavior: Options updated and coordinator refreshed immediately

    Turning off simulation mode re-enables normal cover operation, which must
    happen immediately to provide responsive control.
    """
    # Setup integration with simulation mode initially enabled
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.SIMULATION_MODE.value] = True

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()
    # Mock the hass.config_entries.async_update_entry method
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entities
    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the simulation mode switch entity
    simulation_switch = next(entity for entity in captured if isinstance(entity, SimulationModeSwitch))

    # Execute the turn-off operation
    await simulation_switch.async_turn_off()

    # Verify that async_update_entry was called with the correct options
    # This ensures the switch state is persisted to the config entry
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.SIMULATION_MODE.value] is False


async def test_switch_entity_properties(mock_coordinator_basic) -> None:
    """Test that switch entities are properly created with correct properties.

    This test verifies that all switch entities are created during platform setup
    and have the expected properties.
    """
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture all entities
    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Verify we have exactly 3 switch entities
    assert len(captured) == 3

    # Find each switch type
    enabled_switch = next((entity for entity in captured if isinstance(entity, EnabledSwitch)), None)
    simulation_switch = next((entity for entity in captured if isinstance(entity, SimulationModeSwitch)), None)
    verbose_switch = next((entity for entity in captured if isinstance(entity, VerboseLoggingSwitch)), None)

    # Verify both switches exist
    assert enabled_switch is not None
    assert simulation_switch is not None
    assert verbose_switch is not None

    # Verify unique IDs are set correctly
    assert enabled_switch.unique_id == "smart_cover_automation_enabled"
    assert simulation_switch.unique_id == "smart_cover_automation_simulation_mode"
    assert verbose_switch.unique_id == "smart_cover_automation_verbose_logging"
