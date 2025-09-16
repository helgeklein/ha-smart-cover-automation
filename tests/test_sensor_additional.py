"""Additional tests for sensor entities covering fallbacks and attributes.

This module contains specialized tests for the Smart Cover Automation sensor platform,
focusing on edge cases, data fallbacks, and attribute handling that complement the
main sensor platform tests.

Specific test coverage includes:
1. **Automation Status Summary Generation**: Tests the sensor's ability to create
   human-readable summaries of cover positions and automation activity
2. **Data Fallback Scenarios**: Verifies proper handling when some data is missing
3. **Combined State Reporting**: Tests multi-cover status aggregation and formatting

The automation status sensor is crucial for user visibility into the system's
current state. It provides a text summary that users can easily understand,
showing cover positions, automation activity, and system status in natural language.

These tests ensure the sensor gracefully handles various data states and always
provides meaningful information to users, even when some covers or data points
are unavailable.
"""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import (
    ConfKeys,
)
from custom_components.smart_cover_automation.const import SENSOR_KEY_AUTOMATION_STATUS
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_automation_status_combined_summary_present() -> None:
    """Test that automation status sensor produces a combined-style summary with move indicators.

    This test verifies the sensor's ability to generate human-readable status summaries
    when the automation is actively managing covers. The summary should indicate:
    - Current cover positions (as percentages)
    - Desired cover positions (target positions)
    - Movement indicators when covers are transitioning

    Test scenario:
    - Single cover configuration (cover.one)
    - Cover at 50% position with desired position also at 50%
    - Expected result: Summary contains "moves" and "/" indicating position format

    The combined summary format helps users understand both current state and
    automation activity at a glance, showing patterns like "Cover: 45/60%" where
    the first number is current position and second is target position.
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    # Setup coordinator with cover position data
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))
    coordinator.data = {
        ConfKeys.COVERS.value: {
            "cover.one": {
                ATTR_CURRENT_POSITION: 50,  # Current position: 50%
                "sca_cover_desired_position": 50,  # Target position: 50%
            }
        }
    }
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    config_entry.runtime_data.coordinator = coordinator

    # Capture entities that would be added to Home Assistant
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the sensor platform to create automation status sensor
    await async_setup_entry_sensor(hass, cast(IntegrationConfigEntry, config_entry), add_entities)

    # Find the automation status sensor by its entity description key
    status = next(e for e in captured if getattr(getattr(e, "entity_description"), "key", "") == SENSOR_KEY_AUTOMATION_STATUS)

    # Get the sensor's native value (the human-readable summary)
    summary = cast(str, getattr(status, "native_value"))

    # Verify the summary contains movement indicators and position formatting
    # "moves" indicates automation activity, "/" separates current/target positions
    assert "moves" in summary and "/" in summary
