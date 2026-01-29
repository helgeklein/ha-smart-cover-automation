"""Focused tests for switch entity setup and properties.

This module contains tests for the Smart Cover Automation switch platform setup,
verifying that all switch entities are properly created and configured.

Note: Turn on/off behavior for EnabledSwitch and SimulationModeSwitch is tested
in test_switches_parameterized.py. VerboseLoggingSwitch edge cases are tested
in test_switch_edge_cases.py.
"""

from __future__ import annotations

from typing import Iterable, cast

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.switch import EnabledSwitch, SimulationModeSwitch, VerboseLoggingSwitch
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)


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
    assert enabled_switch.unique_id == f"{entry.entry_id}_enabled"
    assert simulation_switch.unique_id == f"{entry.entry_id}_simulation_mode"
    assert verbose_switch.unique_id == f"{entry.entry_id}_verbose_logging"
