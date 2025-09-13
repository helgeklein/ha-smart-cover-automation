"""Focused tests for the IntegrationSwitch behavior and edge branches."""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.switch import (
    IntegrationSwitch,
)
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_switch_turn_on_persists_option_and_refresh() -> None:
    entry = MockConfigEntry(create_temperature_config())
    # Start with enabled False to observe change
    entry.runtime_data.config[ConfKeys.ENABLED.value] = False

    hass = MagicMock()
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = coordinator
    entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]

    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    await async_setup_entry_switch(hass, cast(IntegrationConfigEntry, entry), add_entities)
    switch = cast(IntegrationSwitch, captured[0])

    await switch.async_turn_on()

    # Options should be updated with enabled=True and refresh requested
    entry.async_set_options.assert_awaited()  # type: ignore[attr-defined]
    coordinator.async_request_refresh.assert_awaited()


@pytest.mark.asyncio
async def test_switch_turn_off_persists_option_and_refresh() -> None:
    entry = MockConfigEntry(create_temperature_config())
    entry.runtime_data.config[ConfKeys.ENABLED.value] = True

    hass = MagicMock()
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = coordinator
    entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]

    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    await async_setup_entry_switch(hass, cast(IntegrationConfigEntry, entry), add_entities)
    switch = cast(IntegrationSwitch, captured[0])

    await switch.async_turn_off()

    entry.async_set_options.assert_awaited()  # type: ignore[attr-defined]
    coordinator.async_request_refresh.assert_awaited()
