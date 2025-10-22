"""Tests for NighttimeBlockOpeningBinarySensor.

This module tests the nighttime block opening configuration binary sensor.
"""

from __future__ import annotations

from typing import Iterable, cast

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    NighttimeBlockOpeningBinarySensor,
)
from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.const import (
    BINARY_SENSOR_KEY_NIGHTTIME_BLOCK_OPENING,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


async def test_nighttime_block_opening_sensor_enabled(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test nighttime block opening sensor returns True when enabled.

    This test verifies that the nighttime block opening binary sensor correctly
    reports True (Yes) when the nighttime_block_opening configuration is enabled.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True  # type: ignore[attr-defined]

    # Enable nighttime_block_opening in config
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["nighttime_block_opening"] = True

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the nighttime block opening sensor
    nighttime_sensor = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_NIGHTTIME_BLOCK_OPENING),
        None,
    )
    assert nighttime_sensor is not None, "Nighttime block opening sensor not found"
    assert isinstance(nighttime_sensor, NighttimeBlockOpeningBinarySensor)

    # Verify sensor reports True (enabled)
    assert nighttime_sensor.is_on is True


async def test_nighttime_block_opening_sensor_disabled(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test nighttime block opening sensor returns False when disabled.

    This test verifies that the nighttime block opening binary sensor correctly
    reports False (No) when the nighttime_block_opening configuration is disabled.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True  # type: ignore[attr-defined]

    # Disable nighttime_block_opening in config
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["nighttime_block_opening"] = False

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the nighttime block opening sensor
    nighttime_sensor = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_NIGHTTIME_BLOCK_OPENING),
        None,
    )
    assert nighttime_sensor is not None, "Nighttime block opening sensor not found"
    assert isinstance(nighttime_sensor, NighttimeBlockOpeningBinarySensor)

    # Verify sensor reports False (disabled)
    assert nighttime_sensor.is_on is False
