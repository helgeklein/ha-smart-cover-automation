"""Tests for AutomationDisabledTimeRangeSensor.

This module tests the automation disabled time range configuration sensor.
"""

from __future__ import annotations

from datetime import time
from typing import Iterable, cast

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.const import (
    SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    AutomationDisabledTimeRangeSensor,
)
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)


async def test_automation_disabled_time_range_sensor_disabled(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test automation disabled time range sensor returns 'off' when disabled.

    This test verifies that the sensor correctly reports 'off' when the
    automation_disabled_time_range configuration is disabled.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Disable automation_disabled_time_range in config
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["automation_disabled_time_range"] = False

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the sensor platform
    await async_setup_entry_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the automation disabled time range sensor
    time_range_sensor = next(
        (entity for entity in captured if entity.entity_description.key == SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE),
        None,
    )
    assert time_range_sensor is not None, "Automation disabled time range sensor not found"
    assert isinstance(time_range_sensor, AutomationDisabledTimeRangeSensor)

    # Verify sensor reports "off" (disabled)
    assert time_range_sensor.native_value == "off"


async def test_automation_disabled_time_range_sensor_enabled_default_times(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test automation disabled time range sensor with enabled and default times.

    This test verifies that the sensor correctly formats the time range
    when the automation_disabled_time_range is enabled with default times.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Enable automation_disabled_time_range with default times (22:00-06:00)
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["automation_disabled_time_range"] = True
    mock_config_entry_basic.options["automation_disabled_time_range_start"] = time(22, 0, 0)
    mock_config_entry_basic.options["automation_disabled_time_range_end"] = time(6, 0, 0)

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the sensor platform
    await async_setup_entry_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the automation disabled time range sensor
    time_range_sensor = next(
        (entity for entity in captured if entity.entity_description.key == SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE),
        None,
    )
    assert time_range_sensor is not None, "Automation disabled time range sensor not found"
    assert isinstance(time_range_sensor, AutomationDisabledTimeRangeSensor)

    # Verify sensor reports formatted time range
    assert time_range_sensor.native_value == "22:00-06:00"


async def test_automation_disabled_time_range_sensor_enabled_custom_times(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test automation disabled time range sensor with enabled and custom times.

    This test verifies that the sensor correctly formats various custom time ranges.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Enable automation_disabled_time_range with custom times
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["automation_disabled_time_range"] = True
    mock_config_entry_basic.options["automation_disabled_time_range_start"] = time(14, 30, 0)
    mock_config_entry_basic.options["automation_disabled_time_range_end"] = time(16, 45, 0)

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the sensor platform
    await async_setup_entry_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the automation disabled time range sensor
    time_range_sensor = next(
        (entity for entity in captured if entity.entity_description.key == SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE),
        None,
    )
    assert time_range_sensor is not None, "Automation disabled time range sensor not found"
    assert isinstance(time_range_sensor, AutomationDisabledTimeRangeSensor)

    # Verify sensor reports formatted time range with custom times
    assert time_range_sensor.native_value == "14:30-16:45"


async def test_automation_disabled_time_range_sensor_enabled_edge_times(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test automation disabled time range sensor with edge case times.

    This test verifies correct formatting for edge cases like midnight, single digits, etc.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Enable automation_disabled_time_range with edge case times (00:05-09:09)
    mock_config_entry_basic.runtime_data.coordinator = coordinator
    mock_config_entry_basic.options["automation_disabled_time_range"] = True
    mock_config_entry_basic.options["automation_disabled_time_range_start"] = time(0, 5, 0)
    mock_config_entry_basic.options["automation_disabled_time_range_end"] = time(9, 9, 0)

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the sensor platform
    await async_setup_entry_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the automation disabled time range sensor
    time_range_sensor = next(
        (entity for entity in captured if entity.entity_description.key == SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE),
        None,
    )
    assert time_range_sensor is not None, "Automation disabled time range sensor not found"
    assert isinstance(time_range_sensor, AutomationDisabledTimeRangeSensor)

    # Verify sensor properly zero-pads single digit hours and minutes
    assert time_range_sensor.native_value == "00:05-09:09"
