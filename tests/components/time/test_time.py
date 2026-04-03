"""Tests for the time platform entities."""

from __future__ import annotations

from datetime import time
from types import SimpleNamespace
from typing import Iterable, cast
from unittest.mock import MagicMock, Mock

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.const import (
    TIME_KEY_MORNING_OPENING_EXTERNAL_TIME,
    MorningOpeningMode,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.time import (
    MorningOpeningExternalTime,
)
from custom_components.smart_cover_automation.time import (
    async_setup_entry as async_setup_entry_time,
)


#
# _capture_added_entities
#
def _capture_added_entities() -> tuple[list[Entity], object]:
    """Create an entity collector callback for platform setup tests."""

    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Collect entities added by the platform setup."""

        captured.extend(list(new_entities))

    return captured, add_entities


#
# test_async_setup_entry_adds_external_time_entity
#
async def test_async_setup_entry_adds_external_time_entity(mock_coordinator_basic) -> None:
    """External morning opening mode should create one time entity."""

    entry = mock_coordinator_basic.config_entry
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    mock_coordinator_basic._resolved_settings = Mock(return_value=SimpleNamespace(morning_opening_mode=MorningOpeningMode.EXTERNAL))
    captured, add_entities = _capture_added_entities()

    await async_setup_entry_time(
        mock_coordinator_basic.hass,
        cast(IntegrationConfigEntry, entry),
        add_entities,
    )

    assert len(captured) == 1
    assert isinstance(captured[0], MorningOpeningExternalTime)
    assert captured[0].unique_id == f"{entry.entry_id}_{TIME_KEY_MORNING_OPENING_EXTERNAL_TIME}"


#
# test_async_setup_entry_skips_time_entity_when_not_external
#
async def test_async_setup_entry_skips_time_entity_when_not_external(mock_coordinator_basic) -> None:
    """Non-external morning opening modes should not create time entities."""

    entry = mock_coordinator_basic.config_entry
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = mock_coordinator_basic
    mock_coordinator_basic._resolved_settings = Mock(return_value=SimpleNamespace(morning_opening_mode=MorningOpeningMode.FIXED_TIME))
    captured, add_entities = _capture_added_entities()

    await async_setup_entry_time(
        mock_coordinator_basic.hass,
        cast(IntegrationConfigEntry, entry),
        add_entities,
    )

    assert captured == []


#
# test_morning_opening_external_time_metadata_and_native_value
#
def test_morning_opening_external_time_metadata_and_native_value(mock_coordinator_basic) -> None:
    """The time entity should expose metadata and parse stored option values."""

    entry = mock_coordinator_basic.config_entry
    entity = MorningOpeningExternalTime(mock_coordinator_basic)

    assert entity.entity_description.key == TIME_KEY_MORNING_OPENING_EXTERNAL_TIME
    assert entity.entity_description.translation_key == TIME_KEY_MORNING_OPENING_EXTERNAL_TIME
    assert entity.entity_description.icon == "mdi:weather-sunset-up"
    assert entity.native_value is None

    entry.options[TIME_KEY_MORNING_OPENING_EXTERNAL_TIME] = "08:15:00"
    assert entity.native_value == time(8, 15)


#
# test_morning_opening_external_time_invalid_native_value_returns_none
#
def test_morning_opening_external_time_invalid_native_value_returns_none(mock_coordinator_basic) -> None:
    """Invalid stored values should be treated as missing time values."""

    entry = mock_coordinator_basic.config_entry
    entry.options[TIME_KEY_MORNING_OPENING_EXTERNAL_TIME] = "not-a-time"

    entity = MorningOpeningExternalTime(mock_coordinator_basic)

    assert entity.native_value is None


#
# test_morning_opening_external_time_async_set_value_persists_isoformat
#
async def test_morning_opening_external_time_async_set_value_persists_isoformat(mock_coordinator_basic) -> None:
    """Setting a new time value should persist it to config entry options."""

    entity = MorningOpeningExternalTime(mock_coordinator_basic)
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    await entity.async_set_value(time(7, 45))

    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_kwargs = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
    assert options[TIME_KEY_MORNING_OPENING_EXTERNAL_TIME] == "07:45:00"
