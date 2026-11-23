"""Tests for the evening closure and tilt angle control select entities.

Covers the select entities themselves and the coordinator properties and
setters they are backed by.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    SELECT_KEY_EVENING_CLOSURE,
    SELECT_KEY_TILT_CONTROL,
    EveningClosureControl,
    TiltControl,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.select import EveningClosureControlSelect, TiltControlSelect

from ...conftest import MockConfigEntry, create_temperature_config, set_test_options


@pytest.fixture
def coordinator() -> DataUpdateCoordinator:
    """Create a coordinator whose config entry updates are captured by a mock."""

    hass = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    config_entry = MockConfigEntry(create_temperature_config())
    return DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))


def _set_options(coordinator: DataUpdateCoordinator, **options: object) -> None:
    """Add options to the coordinator's config entry for test setup."""

    entry = coordinator.config_entry
    set_test_options(entry, {**dict(entry.options), **options})  # type: ignore[arg-type]


def _saved_options(coordinator: DataUpdateCoordinator) -> dict:
    """Return the options passed to the last config entry update."""

    return coordinator.hass.config_entries.async_update_entry.call_args[1]["options"]


class TestEveningClosureControlSelect:
    """Evening closure select."""

    def test_entity_properties(self, coordinator) -> None:
        """Key, unique ID and options match the evening closure enum."""

        select = EveningClosureControlSelect(coordinator)

        assert select.entity_description.key == SELECT_KEY_EVENING_CLOSURE
        assert select.entity_description.translation_key == SELECT_KEY_EVENING_CLOSURE
        assert select.unique_id == f"{coordinator.config_entry.entry_id}_{SELECT_KEY_EVENING_CLOSURE}"
        assert select.options == [value.value for value in EveningClosureControl]

    @pytest.mark.parametrize("value", list(EveningClosureControl), ids=lambda v: v.value)
    def test_current_option_returns_stored_value(self, coordinator, value: EveningClosureControl) -> None:
        """The current option is the evening closure setting from the configuration wizard."""

        _set_options(coordinator, **{ConfKeys.EVENING_CLOSURE.value: value.value})

        assert EveningClosureControlSelect(coordinator).current_option == value.value

    def test_current_option_defaults_to_off(self, coordinator) -> None:
        """Without a stored value, evening closure is off."""

        assert EveningClosureControlSelect(coordinator).current_option == EveningClosureControl.OFF.value

    async def test_select_option_calls_coordinator_setter(self, coordinator) -> None:
        """Selecting an option delegates to the coordinator setter."""

        coordinator.async_set_evening_closure_control = AsyncMock()
        select = EveningClosureControlSelect(coordinator)

        await select.async_select_option(EveningClosureControl.CLOSE_ONCE.value)

        coordinator.async_set_evening_closure_control.assert_awaited_once_with(EveningClosureControl.CLOSE_ONCE)

    @pytest.mark.parametrize("value", list(EveningClosureControl), ids=lambda v: v.value)
    async def test_setter_persists_value(self, coordinator, value: EveningClosureControl) -> None:
        """Every evening closure option is persisted to the same setting the configuration wizard uses."""

        await coordinator.async_set_evening_closure_control(value)

        assert _saved_options(coordinator)[ConfKeys.EVENING_CLOSURE.value] == value

    async def test_setter_rejects_invalid_value(self, coordinator) -> None:
        """Invalid values raise and don't update the config entry."""

        with pytest.raises(ValueError, match="Invalid evening closure"):
            await coordinator.async_set_evening_closure_control("invalid")  # type: ignore[arg-type]

        coordinator.hass.config_entries.async_update_entry.assert_not_called()


class TestTiltControlSelect:
    """Tilt angle control select."""

    def test_entity_properties(self, coordinator) -> None:
        """Key, unique ID and options match the tilt control enum."""

        select = TiltControlSelect(coordinator)

        assert select.entity_description.key == SELECT_KEY_TILT_CONTROL
        assert select.entity_description.translation_key == SELECT_KEY_TILT_CONTROL
        assert select.unique_id == f"{coordinator.config_entry.entry_id}_{SELECT_KEY_TILT_CONTROL}"
        assert select.options == [value.value for value in TiltControl]

    def test_current_option_defaults_to_day_and_night(self, coordinator) -> None:
        """Without a stored value, tilt angle control is active day and night."""

        assert TiltControlSelect(coordinator).current_option == TiltControl.DAY_AND_NIGHT.value

    def test_current_option_returns_stored_value(self, coordinator) -> None:
        """The current option reflects the stored value."""

        _set_options(coordinator, **{ConfKeys.TILT_CONTROL.value: TiltControl.NIGHT_ONLY.value})

        assert TiltControlSelect(coordinator).current_option == TiltControl.NIGHT_ONLY.value

    @pytest.mark.parametrize("value", list(TiltControl), ids=lambda v: v.value)
    async def test_setter_persists_value(self, coordinator, value: TiltControl) -> None:
        """Every tilt control option is persisted to the config entry."""

        await coordinator.async_set_tilt_control(value)

        assert _saved_options(coordinator)[ConfKeys.TILT_CONTROL.value] == value

    async def test_setter_rejects_invalid_value(self, coordinator) -> None:
        """Invalid values raise and don't update the config entry."""

        with pytest.raises(ValueError, match="Invalid tilt control"):
            await coordinator.async_set_tilt_control("invalid")  # type: ignore[arg-type]

        coordinator.hass.config_entries.async_update_entry.assert_not_called()
