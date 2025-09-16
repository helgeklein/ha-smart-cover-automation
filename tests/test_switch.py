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
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.switch import (
    IntegrationSwitch,
)
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_switch_turn_on_persists_option_and_refresh() -> None:
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
    entry = MockConfigEntry(create_temperature_config())
    # Start with enabled False to observe the state change
    entry.runtime_data.config[ConfKeys.ENABLED.value] = False

    # Setup mock Home Assistant environment
    hass = MagicMock()
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = coordinator
    entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entity
    await async_setup_entry_switch(hass, cast(IntegrationConfigEntry, entry), add_entities)
    switch = cast(IntegrationSwitch, captured[0])

    # Execute the turn-on operation
    await switch.async_turn_on()

    # Verify that options are updated (state persistence)
    # This ensures the switch state survives Home Assistant restarts
    entry.async_set_options.assert_awaited()  # type: ignore[attr-defined]

    # Verify that coordinator refresh is triggered (immediate effect)
    # This ensures automation starts immediately without waiting for next update cycle
    coordinator.async_request_refresh.assert_awaited()


@pytest.mark.asyncio
async def test_switch_turn_off_persists_option_and_refresh() -> None:
    """Test that turning the switch OFF persists the disabled state and triggers refresh.

    This test verifies the complete turn-off sequence for the automation switch:
    1. State persistence through Home Assistant's options system
    2. Immediate coordinator refresh to apply the new state
    3. Proper deactivation of automation logic

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
    entry = MockConfigEntry(create_temperature_config())
    entry.runtime_data.config[ConfKeys.ENABLED.value] = True  # Start enabled to observe disable

    # Setup mock Home Assistant environment
    hass = MagicMock()
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = coordinator
    entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]

    # Capture entities created by the switch platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the switch platform and capture the switch entity
    await async_setup_entry_switch(hass, cast(IntegrationConfigEntry, entry), add_entities)
    switch = cast(IntegrationSwitch, captured[0])

    # Execute the turn-off operation
    await switch.async_turn_off()

    # Verify that options are updated (state persistence)
    # This ensures the disabled state survives Home Assistant restarts
    entry.async_set_options.assert_awaited()  # type: ignore[attr-defined]

    # Verify that coordinator refresh is triggered (immediate effect)
    # This ensures automation stops immediately without waiting for next update cycle
    coordinator.async_request_refresh.assert_awaited()
