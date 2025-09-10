"""Tests for the Automation Status sensor."""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
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
    config[ConfKeys.TEMPERATURE_SENSOR.value] = "sensor.temperature"
    config[ConfKeys.TEMPERATURE_HYSTERESIS.value] = 0.7
    config[ConfKeys.MIN_POSITION_DELTA.value] = 10

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Simulate coordinator data for two covers (one will move)
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    # Combined is the only mode; no automation_type key is used anymore.
    coordinator.data = {
        ConfKeys.COVERS.value: {
            "cover.one": {
                "current_temp": 22.5,
                "min_temp": config[ConfKeys.MIN_TEMPERATURE.value],
                "max_temp": config[ConfKeys.MAX_TEMPERATURE.value],
                "current_position": 50,
                "desired_position": 40,  # movement
            },
            "cover.two": {
                "current_temp": 22.5,
                "min_temp": config[ConfKeys.MIN_TEMPERATURE.value],
                "max_temp": config[ConfKeys.MAX_TEMPERATURE.value],
                "current_position": 100,
                "desired_position": 100,  # no movement
            },
        }
    }

    # Summary string (robust to symbol differences)
    summary = cast(str, getattr(status, "native_value"))
    assert "Temp " in summary
    assert "22.5" in summary
    assert "moves 1/2" in summary

    # Attributes
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs["enabled"] is True
    assert "automation_type" not in attrs
    assert attrs["covers_total"] == 2
    assert attrs["covers_moved"] == 1
    assert attrs["temp_hysteresis"] == 0.7
    assert attrs["min_position_delta"] == 10
    assert attrs["temperature_sensor"] == "sensor.temperature"
    assert attrs["min_temp"] == config[ConfKeys.MIN_TEMPERATURE.value]
    assert attrs["max_temp"] == config[ConfKeys.MAX_TEMPERATURE.value]
    assert attrs["current_temp"] == 22.5
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
        ConfKeys.COVERS.value: {
            "cover.one": {
                "sun_elevation": 35.0,
                "sun_azimuth": 180.0,
                "elevation_threshold": config[ConfKeys.SUN_ELEVATION_THRESHOLD.value],
                "current_position": 100,
                "desired_position": 80,
            },
            "cover.two": {
                "sun_elevation": 35.0,
                "sun_azimuth": 180.0,
                "elevation_threshold": config[ConfKeys.SUN_ELEVATION_THRESHOLD.value],
                "current_position": 100,
                "desired_position": 100,
            },
        }
    }

    # Summary string
    summary = cast(str, getattr(status, "native_value"))
    # Summary should include Sun info when available
    assert "Sun elev 35.0°" in summary
    assert "moves 1/2" in summary

    # Attributes
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs["enabled"] is True
    assert "automation_type" not in attrs
    assert attrs["covers_total"] == 2
    assert attrs["covers_moved"] == 1
    assert attrs["sun_elevation"] == 35.0
    assert attrs["sun_azimuth"] == 180.0
    assert attrs["elevation_threshold"] == config[ConfKeys.SUN_ELEVATION_THRESHOLD.value]
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
