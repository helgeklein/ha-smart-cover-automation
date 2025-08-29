"""Tests for platform entities: binary_sensor, sensor, and switch."""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.sensor import (
    async_setup_entry as async_setup_entry_sensor,
)
from custom_components.smart_cover_automation.switch import (
    async_setup_entry as async_setup_entry_switch,
)

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_binary_sensor_entity_properties() -> None:
    """Binary sensor setup and property evaluation."""
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    # Coordinator with predefined data and success state
    coordinator = DataUpdateCoordinator(
        hass, cast(IntegrationConfigEntry, config_entry)
    )
    coordinator.data = {"title": "foo"}
    coordinator.last_update_success = True  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data as HA would do
    config_entry.runtime_data.coordinator = coordinator

    captured: list[Entity] = []

    def add_entities(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        captured.extend(list(new_entities))

    await async_setup_entry_binary_sensor(
        hass,
        cast(IntegrationConfigEntry, config_entry),
        add_entities,
    )

    assert len(captured) == 1
    entity = captured[0]

    # available is delegated from CoordinatorEntity; with last_update_success=True it's truthy
    assert cast(bool, getattr(entity, "available")) is True
    # is_on based on coordinator.data["title"] == "foo"
    assert cast(bool, getattr(entity, "is_on")) is True


@pytest.mark.asyncio
async def test_sensor_entity_properties() -> None:
    """Sensor setup and property evaluation."""
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    coordinator = DataUpdateCoordinator(
        hass, cast(IntegrationConfigEntry, config_entry)
    )
    coordinator.data = {"body": "hello"}
    coordinator.last_update_success = True  # type: ignore[attr-defined]
    config_entry.runtime_data.coordinator = coordinator

    captured: list[Entity] = []

    def add_entities(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        captured.extend(list(new_entities))

    await async_setup_entry_sensor(
        hass,
        cast(IntegrationConfigEntry, config_entry),
        add_entities,
    )

    assert len(captured) == 1
    entity = captured[0]
    # available is delegated from CoordinatorEntity; with last_update_success=True it's truthy
    assert cast(bool | None, getattr(entity, "available")) in (True, None)
    # native_value comes from coordinator.data["body"]
    assert getattr(entity, "native_value") == "hello"


@pytest.mark.asyncio
async def test_switch_entity_turn_on_off_and_state() -> None:
    """Switch setup, state, and turn on/off interactions."""
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MockConfigEntry(create_temperature_config())

    coordinator = DataUpdateCoordinator(
        hass, cast(IntegrationConfigEntry, config_entry)
    )
    coordinator.data = {"title": "foo"}
    coordinator.last_update_success = True  # type: ignore[attr-defined]

    # Prevent real refresh logic from running in tests
    coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]

    # Fake client with async_set_title
    client = MagicMock()
    client.async_set_title = AsyncMock()

    config_entry.runtime_data.coordinator = coordinator
    config_entry.runtime_data.client = client

    captured: list[Entity] = []

    def add_entities(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        captured.extend(list(new_entities))

    await async_setup_entry_switch(
        hass,
        cast(IntegrationConfigEntry, config_entry),
        add_entities,
    )

    assert len(captured) == 1
    entity = captured[0]

    # Initial state based on title == "foo"
    assert cast(bool, getattr(entity, "is_on")) is True
    # Access available to exercise property
    assert cast(bool | None, getattr(entity, "available")) in (True, None)

    # Turn on should set title to "bar" and request refresh
    await getattr(entity, "async_turn_on")()
    client.async_set_title.assert_awaited_with("bar")
    coordinator.async_request_refresh.assert_awaited()  # type: ignore[func-returns-value]

    # Turn off should set title to "foo" and request refresh
    await getattr(entity, "async_turn_off")()
    client.async_set_title.assert_awaited_with("foo")
    coordinator.async_request_refresh.assert_awaited()  # type: ignore[func-returns-value]

    # When client is None, calls should not raise and no client method invoked
    other_entry = MockConfigEntry(create_temperature_config())
    other_coordinator = DataUpdateCoordinator(
        hass, cast(IntegrationConfigEntry, other_entry)
    )
    other_coordinator.data = {"title": "baz"}
    other_coordinator.last_update_success = True  # type: ignore[attr-defined]
    other_coordinator.async_request_refresh = AsyncMock()  # type: ignore[assignment]
    other_entry.runtime_data.coordinator = other_coordinator
    other_entry.runtime_data.client = None

    other_captured: list[Entity] = []

    def other_add_entities(
        new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        other_captured.extend(list(new_entities))

    await async_setup_entry_switch(
        hass,
        cast(IntegrationConfigEntry, other_entry),
        other_add_entities,
    )

    other_entity = other_captured[0]
    # Access available on second entity as well
    assert cast(bool | None, getattr(other_entity, "available")) in (True, None)
    await getattr(other_entity, "async_turn_on")()
    await getattr(other_entity, "async_turn_off")()
    # No client to call; just ensure no exception and refresh was requested
    other_coordinator.async_request_refresh.assert_awaited()  # type: ignore[func-returns-value]
