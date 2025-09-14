"""Tests for the Automation Status sensor."""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    SENSOR_ATTR_AUTOMATION_ENABLED,
    SENSOR_ATTR_COVERS_MIN_POSITION_DELTA,
    SENSOR_ATTR_COVERS_NUM_MOVED,
    SENSOR_ATTR_COVERS_NUM_TOTAL,
    SENSOR_ATTR_SUN_AZIMUTH,
    SENSOR_ATTR_SUN_ELEVATION,
    SENSOR_ATTR_SUN_ELEVATION_THRESH,
    SENSOR_ATTR_TEMP_CURRENT,
    SENSOR_ATTR_TEMP_HYSTERESIS,
    SENSOR_ATTR_TEMP_SENSOR_ENTITY_ID,
    SENSOR_ATTR_TEMP_THRESHOLD,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)

from .conftest import MockConfigEntry, create_sun_config, create_temperature_config


async def _capture_entities(hass: HomeAssistant, config: dict[str, object]) -> list[Entity]:
    """Helper to set up the sensor platform and capture created entities."""
    hass_mock = cast(MagicMock, hass)
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass_mock, cast(IntegrationConfigEntry, entry))
    coordinator.data = {}
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    entry.runtime_data.coordinator = coordinator

    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    # Execute platform setup
    await async_setup_entry_sensor(hass_mock, cast(IntegrationConfigEntry, entry), add_entities)

    return captured


def _get_status_entity(entities: list[Entity]) -> Entity:
    return next(e for e in entities if getattr(getattr(e, "entity_description"), "key", "") == "automation_status")


@pytest.mark.asyncio
async def test_status_sensor_combined_summary_and_attributes() -> None:
    """Validate summary and attributes for combined mode."""
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    # Add tuning/options to config
    config[ConfKeys.TEMP_SENSOR_ENTITY_ID.value] = "sensor.temperature"
    config[ConfKeys.TEMP_HYSTERESIS.value] = 0.7
    config[ConfKeys.COVERS_MIN_POSITION_DELTA.value] = 10

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Simulate coordinator data for two covers (one will move)
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    # Combined is the only mode; no automation_type key is used anymore.
    coordinator.data = {
        SENSOR_ATTR_TEMP_CURRENT: 22.5,
        ConfKeys.COVERS.value: {
            "cover.one": {
                ATTR_CURRENT_POSITION: 50,
                "sca_cover_desired_position": 40,  # movement
            },
            "cover.two": {
                ATTR_CURRENT_POSITION: 100,
                "sca_cover_desired_position": 100,  # no movement
            },
        },
    }

    # Summary string (robust to symbol differences)
    summary = cast(str, getattr(status, "native_value"))
    assert "Temp " in summary
    assert "22.5" in summary
    assert "moves 1/2" in summary

    # Attributes
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs[SENSOR_ATTR_AUTOMATION_ENABLED] is True
    assert "automation_type" not in attrs
    assert attrs[SENSOR_ATTR_COVERS_NUM_TOTAL] == 2
    assert attrs[SENSOR_ATTR_COVERS_NUM_MOVED] == 1
    assert attrs[SENSOR_ATTR_TEMP_HYSTERESIS] == 0.7
    assert attrs[SENSOR_ATTR_COVERS_MIN_POSITION_DELTA] == 10
    assert attrs[SENSOR_ATTR_TEMP_SENSOR_ENTITY_ID] == "sensor.temperature"
    assert attrs[SENSOR_ATTR_TEMP_THRESHOLD] == config[ConfKeys.TEMP_THRESHOLD.value]
    assert attrs[SENSOR_ATTR_TEMP_CURRENT] == 22.5
    assert isinstance(attrs[ConfKeys.COVERS.value], dict)


@pytest.mark.asyncio
async def test_status_sensor_combined_sun_attributes_present() -> None:
    """Validate sun attributes presence in combined mode."""
    hass = MagicMock(spec=HomeAssistant)
    config = create_sun_config()
    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    # Combined-only, no automation_type in config
    coordinator.data = {
        SENSOR_ATTR_SUN_ELEVATION: 35.0,
        SENSOR_ATTR_SUN_AZIMUTH: 180.0,
        ConfKeys.COVERS.value: {
            "cover.one": {
                ATTR_CURRENT_POSITION: 100,
                "sca_cover_desired_position": 80,
            },
            "cover.two": {
                ATTR_CURRENT_POSITION: 100,
                "sca_cover_desired_position": 100,
            },
        },
    }

    # Summary string
    summary = cast(str, getattr(status, "native_value"))
    # Summary should include Sun info when available
    assert "Sun elev 35.0°" in summary
    assert "moves 1/2" in summary

    # Attributes
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs[SENSOR_ATTR_AUTOMATION_ENABLED] is True
    assert "automation_type" not in attrs
    assert attrs[SENSOR_ATTR_COVERS_NUM_TOTAL] == 2
    assert attrs[SENSOR_ATTR_COVERS_NUM_MOVED] == 1
    assert attrs[SENSOR_ATTR_SUN_ELEVATION] == 35.0
    assert attrs[SENSOR_ATTR_SUN_AZIMUTH] == 180.0
    assert attrs[SENSOR_ATTR_SUN_ELEVATION_THRESH] == config[ConfKeys.SUN_ELEVATION_THRESHOLD.value]
    assert isinstance(attrs[ConfKeys.COVERS.value], dict)


@pytest.mark.asyncio
async def test_status_sensor_disabled() -> None:
    """When globally disabled, summary is 'Disabled'."""
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    config[ConfKeys.ENABLED.value] = False

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Even with dummy data, 'enabled' False should short-circuit
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.data = {ConfKeys.COVERS.value: {}}
    val = cast(str, getattr(status, "native_value"))
    assert val == "Disabled"
