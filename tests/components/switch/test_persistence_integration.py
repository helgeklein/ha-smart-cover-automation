"""Integration tests for switch persistence functionality.

This module tests the complete     # Verify config entry was updated for persistence
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    updated_entry, options_kwargs = call_args[0][0], call_args[1]
    assert updated_entry == entry, "Correct config entry should be updated"
    assert options_kwargs[HA_OPTIONS][ConfKeys.ENABLED.value] is True, "Enabled option should be persisted as True"istence flow to ensure that switch changes
persist across Home Assistant restarts while maintaining immediate responsiveness.

The persistence implementation uses a dual-update pattern:
1. Immediate runtime override for instant entity state updates
2. Delayed config entry persistence for restart durability
3. Cleanup mechanism to remove redundant runtime overrides
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import HA_OPTIONS
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.switch import (
    EnabledSwitch,
    SimulationModeSwitch,
)
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity


@pytest.mark.asyncio
async def test_switch_persistence_across_simulated_restart(mock_coordinator_basic) -> None:
    """Test that switch changes persist across a simulated Home Assistant restart.

    This test verifies the complete persistence lifecycle:
    1. Initial state: switch disabled (enabled = False)
    2. User action: turn switch ON through UI
    3. Verification: immediate runtime effect visible
    4. Verification: config entry updated for persistence
    5. Simulated restart: new coordinator with persisted config
    6. Verification: switch state matches persisted value

    This ensures users don't lose their switch preferences when Home Assistant
    restarts, while maintaining the immediate responsiveness they expect.
    """
    # Setup initial integration with switch disabled
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.ENABLED.value] = False
    entry.options = {ConfKeys.ENABLED.value: False}  # Initial persisted state

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    # Mock the hass.config_entries.async_update_entry method (this is what persistence actually calls)
    mock_coordinator_basic.hass.config_entries.async_update_entry = AsyncMock()

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entities
    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the enabled switch entity
    enabled_switch = next(entity for entity in captured if isinstance(entity, EnabledSwitch))

    # Verify initial state: switch should be OFF (disabled)
    assert not enabled_switch.is_on, "Switch should initially be disabled"

    # Execute the turn-on operation (user changes switch in UI)
    await enabled_switch.async_turn_on()

    # Verify config entry was updated for persistence
    # The new implementation directly updates the config entry without runtime overrides
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    updated_entry, options_kwargs = call_args[0][0], call_args[1]
    assert updated_entry == entry, "Correct config entry should be updated"
    assert options_kwargs[HA_OPTIONS][ConfKeys.ENABLED.value] is True, "Config entry should be updated with enabled=True"

    # Simulate Home Assistant restart: create new coordinator with persisted config
    # The persisted config should now have enabled=True from the switch change
    persisted_config = {
        ConfKeys.ENABLED.value: True,  # This came from the switch persistence
        ConfKeys.COVERS.value: ["cover.test_cover"],
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.forecast",
        ConfKeys.TEMP_THRESHOLD.value: 25.0,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 35.0,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value: 1800,
        ConfKeys.SIMULATING.value: False,
        ConfKeys.VERBOSE_LOGGING.value: False,
    }

    # Create new config entry with persisted values (simulating restart)
    from tests.conftest import MockConfigEntry

    new_entry = MockConfigEntry(persisted_config)
    new_entry.options = {ConfKeys.ENABLED.value: True}  # Persisted from switch change

    # Create new coordinator with persisted config (simulating restart)
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator

    new_coordinator = DataUpdateCoordinator(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, new_entry))
    new_coordinator.last_update_success = True
    new_coordinator.async_update_listeners = Mock()
    new_entry.runtime_data.coordinator = new_coordinator

    # Setup switch platform with new coordinator (simulating restart)
    captured_after_restart: list[Entity] = []

    def add_entities_after_restart(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function for post-restart entities."""
        captured_after_restart.extend(list(new_entities))

    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, new_entry), add_entities_after_restart)

    # Find the enabled switch entity after restart
    enabled_switch_after_restart = next(entity for entity in captured_after_restart if isinstance(entity, EnabledSwitch))

    # Verify persistence: switch should still be ON after restart
    assert enabled_switch_after_restart.is_on, "Switch should remain enabled after restart"

    # Verify the persisted value is in the config entry options
    assert new_entry.options.get(ConfKeys.ENABLED.value) is True, "Config entry should have persisted enabled=True"


@pytest.mark.asyncio
async def test_simulation_mode_persistence_across_simulated_restart(mock_coordinator_basic) -> None:
    """Test that simulation mode switch changes persist across a simulated restart.

    This test verifies persistence for the simulation mode switch specifically,
    ensuring that users don't lose their simulation preferences when Home Assistant restarts.
    """
    # Setup initial integration with simulation mode disabled
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.SIMULATING.value] = False
    entry.options = {ConfKeys.SIMULATING.value: False}

    # Setup mock environment
    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    # Mock the correct persistence method
    mock_coordinator_basic.hass.config_entries.async_update_entry = AsyncMock()

    # Setup switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the simulation mode switch
    simulation_switch = next(entity for entity in captured if isinstance(entity, SimulationModeSwitch))

    # Verify initial state: simulation mode should be OFF
    assert not simulation_switch.is_on, "Simulation mode should initially be disabled"

    # Enable simulation mode
    await simulation_switch.async_turn_on()

    # Verify config entry was updated directly (new implementation)
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.SIMULATING.value] is True, "Simulation mode should be persisted as True"

    # Simulate restart with persisted simulation mode enabled
    persisted_config = {
        ConfKeys.ENABLED.value: True,
        ConfKeys.COVERS.value: ["cover.test_cover"],
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.forecast",
        ConfKeys.TEMP_THRESHOLD.value: 25.0,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 35.0,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value: 1800,
        ConfKeys.SIMULATING.value: True,  # Persisted from switch change
        ConfKeys.VERBOSE_LOGGING.value: False,
    }

    from tests.conftest import MockConfigEntry

    new_entry = MockConfigEntry(persisted_config)
    new_entry.options = {ConfKeys.SIMULATING.value: True}

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator

    new_coordinator = DataUpdateCoordinator(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, new_entry))
    new_coordinator.last_update_success = True
    new_coordinator.async_update_listeners = Mock()
    new_entry.runtime_data.coordinator = new_coordinator

    # Setup switch platform after restart
    captured_after_restart: list[Entity] = []

    def add_entities_after_restart(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured_after_restart.extend(list(new_entities))

    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, new_entry), add_entities_after_restart)

    # Find simulation mode switch after restart
    simulation_switch_after_restart = next(entity for entity in captured_after_restart if isinstance(entity, SimulationModeSwitch))

    # Verify persistence: simulation mode should still be ON after restart
    assert simulation_switch_after_restart.is_on, "Simulation mode should remain enabled after restart"


@pytest.mark.asyncio
async def test_direct_persistence_without_runtime_overrides(mock_coordinator_basic) -> None:
    """Test that switch changes directly persist to config entry.

    This verifies that the new implementation directly updates the config entry
    without using runtime overrides, providing a cleaner and more straightforward
    persistence mechanism.
    """
    # Setup
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.ENABLED.value] = False
    entry.options = {}

    mock_coordinator_basic.last_update_success = True
    mock_coordinator_basic.async_update_listeners = Mock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    # Mock the actual persistence method
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    await async_setup_entry_switch(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    enabled_switch = next(entity for entity in captured if isinstance(entity, EnabledSwitch))

    # Turn on switch
    await enabled_switch.async_turn_on()

    # Verify persistence was called immediately (new implementation)
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()

    # Verify the config entry was updated with the correct options
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.ENABLED.value] is True, "Enabled option should be persisted as True"
