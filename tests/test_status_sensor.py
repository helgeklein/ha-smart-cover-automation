"""Tests for the Automation Status sensor."""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.const import (
    AUTOMATION_TYPE_SUN,
    AUTOMATION_TYPE_TEMPERATURE,
    CONF_AUTOMATION_TYPE,
    CONF_ENABLED,
    CONF_MAX_TEMP,
    CONF_MIN_POSITION_DELTA,
    CONF_MIN_TEMP,
    CONF_SUN_ELEVATION_THRESHOLD,
    CONF_TEMP_HYSTERESIS,
    CONF_TEMP_SENSOR,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)

from .conftest import MockConfigEntry, create_sun_config, create_temperature_config


async def _capture_entities(
    hass: HomeAssistant, config: dict[str, object]
) -> list[Entity]:
    """Helper to set up the sensor platform and capture created entities."""
    hass_mock = cast(MagicMock, hass)
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass_mock, cast(IntegrationConfigEntry, entry))
    coordinator.data = {}
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    entry.runtime_data.coordinator = coordinator

    captured: list[Entity] = []

    def add_entities(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    # Execute platform setup
    await async_setup_entry_sensor(
        hass_mock, cast(IntegrationConfigEntry, entry), add_entities
    )

    return captured


def _get_status_entity(entities: list[Entity]) -> Entity:
    return next(
        e
        for e in entities
        if getattr(getattr(e, "entity_description"), "key", "") == "automation_status"
    )


@pytest.mark.asyncio
async def test_status_sensor_temperature_summary_and_attributes() -> None:
    """Validate summary and attributes for temperature mode."""
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    # Add tuning/options to config
    config[CONF_TEMP_SENSOR] = "sensor.temperature"
    config[CONF_TEMP_HYSTERESIS] = 0.7
    config[CONF_MIN_POSITION_DELTA] = 10

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Simulate coordinator data for two covers (one will move)
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.config_entry.runtime_data.config[CONF_AUTOMATION_TYPE] = (
        AUTOMATION_TYPE_TEMPERATURE
    )
    coordinator.data = {
        "covers": {
            "cover.one": {
                "current_temp": 22.5,
                "min_temp": config[CONF_MIN_TEMP],
                "max_temp": config[CONF_MAX_TEMP],
                "current_position": 50,
                "desired_position": 40,  # movement
            },
            "cover.two": {
                "current_temp": 22.5,
                "min_temp": config[CONF_MIN_TEMP],
                "max_temp": config[CONF_MAX_TEMP],
                "current_position": 100,
                "desired_position": 100,  # no movement
            },
        }
    }

    # Summary string (robust to symbol differences)
    summary = cast(str, getattr(status, "native_value"))
    assert summary.startswith("Temp ")
    assert "22.5" in summary
    assert "moves 1/2" in summary

    # Attributes
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs["enabled"] is True
    assert attrs["automation_type"] == AUTOMATION_TYPE_TEMPERATURE
    assert attrs["covers_total"] == 2
    assert attrs["covers_moved"] == 1
    assert attrs["temp_hysteresis"] == 0.7
    assert attrs["min_position_delta"] == 10
    assert attrs["temperature_sensor"] == "sensor.temperature"
    assert attrs["min_temp"] == config[CONF_MIN_TEMP]
    assert attrs["max_temp"] == config[CONF_MAX_TEMP]
    assert attrs["current_temp"] == 22.5
    assert isinstance(attrs["covers"], dict)


@pytest.mark.asyncio
async def test_status_sensor_sun_summary_and_attributes() -> None:
    """Validate summary and attributes for sun mode."""
    hass = MagicMock(spec=HomeAssistant)
    config = create_sun_config()
    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.config_entry.runtime_data.config[CONF_AUTOMATION_TYPE] = (
        AUTOMATION_TYPE_SUN
    )
    coordinator.data = {
        "covers": {
            "cover.one": {
                "sun_elevation": 35.0,
                "sun_azimuth": 180.0,
                "elevation_threshold": config[CONF_SUN_ELEVATION_THRESHOLD],
                "current_position": 100,
                "desired_position": 80,
            },
            "cover.two": {
                "sun_elevation": 35.0,
                "sun_azimuth": 180.0,
                "elevation_threshold": config[CONF_SUN_ELEVATION_THRESHOLD],
                "current_position": 100,
                "desired_position": 100,
            },
        }
    }

    # Summary string
    summary = cast(str, getattr(status, "native_value"))
    assert summary.startswith("Sun elev ")
    assert "35.0" in summary
    assert "moves 1/2" in summary

    # Attributes
    attrs = cast(dict, getattr(status, "extra_state_attributes"))
    assert attrs["enabled"] is True
    assert attrs["automation_type"] == AUTOMATION_TYPE_SUN
    assert attrs["covers_total"] == 2
    assert attrs["covers_moved"] == 1
    assert attrs["sun_elevation"] == 35.0
    assert attrs["sun_azimuth"] == 180.0
    assert attrs["elevation_threshold"] == config[CONF_SUN_ELEVATION_THRESHOLD]
    assert isinstance(attrs["covers"], dict)


@pytest.mark.asyncio
async def test_status_sensor_disabled() -> None:
    """When globally disabled, summary is 'Disabled'."""
    hass = MagicMock(spec=HomeAssistant)
    config = create_temperature_config()
    config[CONF_ENABLED] = False

    entities = await _capture_entities(hass, config)
    status = _get_status_entity(entities)

    # Even with dummy data, 'enabled' False should short-circuit
    coordinator = cast(DataUpdateCoordinator, getattr(status, "coordinator"))
    coordinator.data = {"covers": {}}
    val = cast(str, getattr(status, "native_value"))
    assert val == "Disabled"
