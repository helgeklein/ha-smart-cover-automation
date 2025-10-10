"""Tests for the Last Movement Timestamp sensor.

This module contains tests for the Last Movement Timestamp sensor,
which reports the timestamp of the most recent cover movement across all covers
in the automation.

Key testing areas include:
1. **Timestamp Reporting**: Tests that the sensor correctly reports movement timestamps
2. **No Movement Handling**: Tests behavior when no movements have been recorded
3. **Multiple Covers**: Tests finding the most recent timestamp across multiple covers
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator

from ...conftest import capture_platform_entities, create_temperature_config


def _get_timestamp_sensor(entities: list[Entity]) -> Entity:
    """Helper function to extract the timestamp sensor from a list of entities.

    Args:
        entities: List of entities to search through

    Returns:
        The last movement timestamp sensor entity

    Raises:
        StopIteration: If no timestamp sensor is found in the entity list
    """
    return next(e for e in entities if getattr(getattr(e, "entity_description"), "key", "") == SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP)


async def test_timestamp_sensor_with_single_movement() -> None:
    """Test sensor reports timestamp when a single cover movement exists.

    Test scenario:
    - One cover with position history
    - Single movement recorded with timestamp

    Expected behavior:
    - Sensor returns datetime object
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()

    entities = await capture_platform_entities(hass, config, "sensor")
    sensor = _get_timestamp_sensor(entities)

    # Simulate coordinator data
    coordinator = cast(DataUpdateCoordinator, getattr(sensor, "coordinator"))
    coordinator.data = {ConfKeys.COVERS.value: {"cover.one": {}}}

    # Add position history with timestamp
    now = datetime.now(timezone.utc)
    coordinator._cover_pos_history_mgr.add("cover.one", 50, cover_moved=True, timestamp=now)

    # Verify sensor returns datetime object
    timestamp = cast(datetime, getattr(sensor, "native_value"))
    assert timestamp == now


async def test_timestamp_sensor_with_multiple_movements() -> None:
    """Test sensor reports the most recent timestamp across multiple covers.

    Test scenario:
    - Multiple covers with position history
    - Different movement timestamps
    - Most recent movement should be reported

    Expected behavior:
    - Sensor returns the most recent datetime object
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()

    entities = await capture_platform_entities(hass, config, "sensor")
    sensor = _get_timestamp_sensor(entities)

    # Simulate coordinator data
    coordinator = cast(DataUpdateCoordinator, getattr(sensor, "coordinator"))
    coordinator.data = {
        ConfKeys.COVERS.value: {
            "cover.one": {},
            "cover.two": {},
            "cover.three": {},
        }
    }

    # Add movements at different times
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=2)
    older_time = now - timedelta(hours=5)

    coordinator._cover_pos_history_mgr.add("cover.one", 50, cover_moved=True, timestamp=older_time)
    coordinator._cover_pos_history_mgr.add("cover.two", 75, cover_moved=True, timestamp=old_time)
    coordinator._cover_pos_history_mgr.add("cover.three", 100, cover_moved=True, timestamp=now)  # Most recent

    # Verify sensor returns the most recent datetime
    timestamp = cast(datetime, getattr(sensor, "native_value"))
    assert timestamp == now


async def test_timestamp_sensor_no_movement_history() -> None:
    """Test sensor returns None when no cover movement history exists.

    Test scenario:
    - Covers configured but no movement history

    Expected behavior:
    - Sensor returns None
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()

    entities = await capture_platform_entities(hass, config, "sensor")
    sensor = _get_timestamp_sensor(entities)

    # Simulate coordinator data without any position history
    coordinator = cast(DataUpdateCoordinator, getattr(sensor, "coordinator"))
    coordinator.data = {ConfKeys.COVERS.value: {"cover.one": {}}}

    # Verify sensor returns None when no history
    timestamp = getattr(sensor, "native_value")
    assert timestamp is None


async def test_timestamp_sensor_no_coordinator_data() -> None:
    """Test sensor returns None when coordinator has no data.

    Test scenario:
    - Coordinator data is None or empty

    Expected behavior:
    - Sensor returns None gracefully
    """
    # Setup mock Home Assistant environment
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()

    entities = await capture_platform_entities(hass, config, "sensor")
    sensor = _get_timestamp_sensor(entities)

    # Simulate coordinator with no data (empty dict)
    coordinator = cast(DataUpdateCoordinator, getattr(sensor, "coordinator"))
    coordinator.data = {}

    # Verify sensor returns None when no data
    timestamp = getattr(sensor, "native_value")
    assert timestamp is None
