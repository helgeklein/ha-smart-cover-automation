"""Additional tests for sensor entities covering fallbacks and attributes."""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.const import CONF_AUTOMATION_TYPE
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_automation_status_unknown_mode_fallback() -> None:
    """If automation type is unknown, sensor returns a generic summary."""
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    coordinator = DataUpdateCoordinator(
        hass, cast(IntegrationConfigEntry, config_entry)
    )
    coordinator.data = {
        "covers": {
            "cover.one": {
                "current_position": 50,
                "desired_position": 50,
            }
        }
    }
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    config_entry.runtime_data.coordinator = coordinator

    # Force unknown type
    config_entry.runtime_data.config[CONF_AUTOMATION_TYPE] = "unknown"

    captured: list[Entity] = []

    def add_entities(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    await async_setup_entry_sensor(
        hass, cast(IntegrationConfigEntry, config_entry), add_entities
    )

    status = next(
        e
        for e in captured
        if getattr(getattr(e, "entity_description"), "key", "") == "automation_status"
    )

    summary = cast(str, getattr(status, "native_value"))
    assert summary.startswith("Unknown mode")
