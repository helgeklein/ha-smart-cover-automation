"""Tests for __init__ helpers and switch enabled logic via options."""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation import async_get_options_flow
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.settings import SettingsKey
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_async_get_options_flow_returns_handler() -> None:
    entry = MockConfigEntry(create_temperature_config())
    flow = await async_get_options_flow(cast(IntegrationConfigEntry, entry))
    # OptionsFlowHandler has async_step_init attribute
    assert hasattr(flow, "async_step_init")


@pytest.mark.asyncio
async def test_switch_is_on_uses_enabled_option() -> None:
    hass = MagicMock(spec=HomeAssistant)
    entry = MockConfigEntry(create_temperature_config())
    entry.runtime_data.config[SettingsKey.ENABLED.value] = False

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))
    coordinator.data = {"title": "foo"}
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = coordinator
    entry.runtime_data.client = None

    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    await async_setup_entry_switch(hass, cast(IntegrationConfigEntry, entry), add_entities)

    entity = captured[0]
    # With enabled option False, is_on should reflect False regardless of demo title
    assert getattr(entity, "is_on") is False
