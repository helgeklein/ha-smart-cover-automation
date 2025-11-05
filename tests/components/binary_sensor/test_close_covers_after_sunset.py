"""Tests for CloseCoversAfterSunsetBinarySensor.

This module tests the evening closure (close covers after sunset) configuration binary sensor.
"""

from __future__ import annotations

from typing import Iterable, cast

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    CloseCoversAfterSunsetBinarySensor,
)
from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.const import (
    BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


async def test_close_covers_after_sunset_sensor_enabled(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test close covers after sunset sensor returns True when enabled.

    This test verifies that the evening closure binary sensor correctly
    reports True (Yes) when the close_covers_after_sunset configuration is enabled.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Enable close_covers_after_sunset in config
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["close_covers_after_sunset"] = True

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

    # Find the close covers after sunset sensor
    sensor = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET),
        None,
    )
    assert sensor is not None, "Close covers after sunset sensor not found"
    assert isinstance(sensor, CloseCoversAfterSunsetBinarySensor)

    # Verify sensor reports True (enabled)
    assert sensor.is_on is True


async def test_close_covers_after_sunset_sensor_disabled(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test close covers after sunset sensor returns False when disabled.

    This test verifies that the evening closure binary sensor correctly
    reports False (No) when the close_covers_after_sunset configuration is disabled.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Disable close_covers_after_sunset in config
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["close_covers_after_sunset"] = False

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

    # Find the close covers after sunset sensor
    sensor = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET),
        None,
    )
    assert sensor is not None, "Close covers after sunset sensor not found"
    assert isinstance(sensor, CloseCoversAfterSunsetBinarySensor)

    # Verify sensor reports False (disabled)
    assert sensor.is_on is False


async def test_close_covers_after_sunset_sensor_entity_properties(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test close covers after sunset sensor has correct entity properties.

    This test verifies that the sensor has the correct entity properties set.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Enable close_covers_after_sunset in config
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["close_covers_after_sunset"] = True

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

    # Find the close covers after sunset sensor
    sensor = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET),
        None,
    )
    assert sensor is not None, "Close covers after sunset sensor not found"

    # Verify entity properties
    assert sensor.entity_description.key == "close_covers_after_sunset"
    assert sensor.entity_description.translation_key == "close_covers_after_sunset"


async def test_close_covers_after_sunset_sensor_availability(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that sensor inherits availability from coordinator.

    Verifies that the sensor's availability follows the coordinator's state.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Enable close_covers_after_sunset in config
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["close_covers_after_sunset"] = True

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

    # Find the close covers after sunset sensor
    sensor = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET),
        None,
    )
    assert sensor is not None, "Close covers after sunset sensor not found"

    # Test when coordinator is available
    coordinator.last_update_success = True
    assert sensor.available is True

    # Test when coordinator is unavailable
    coordinator.last_update_success = False
    assert sensor.available is False
