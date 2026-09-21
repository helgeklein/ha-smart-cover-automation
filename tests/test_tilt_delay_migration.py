"""Tests for tilt-delay configuration migrations."""

from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation import _async_migrate_tilt_delays_to_seconds, async_migrate_entry, const
from custom_components.smart_cover_automation.config import ConfKeys


@pytest.mark.asyncio
async def test_migrate_legacy_entry_daytime_movement_directions_to_open_only() -> None:
    """Existing entries retain the daytime behavior from before v7."""

    hass = MagicMock()
    entry = MagicMock()
    entry.options = {}
    entry.version = const.CONFIG_ENTRY_VERSION - 1

    assert await async_migrate_entry(hass, entry)

    update_kwargs = hass.config_entries.async_update_entry.call_args.kwargs
    updated_options = update_kwargs["options"]
    assert updated_options[ConfKeys.DAYTIME_MOVEMENT_DIRECTIONS.value] == const.DaytimeMovementDirections.OPEN_ONLY
    assert update_kwargs["version"] == const.CONFIG_ENTRY_VERSION


@pytest.mark.asyncio
async def test_migrate_current_entry_does_not_override_default_daytime_movement_directions() -> None:
    """Fresh entries retain the current default behavior."""

    hass = MagicMock()
    entry = MagicMock()
    entry.options = {}
    entry.version = const.CONFIG_ENTRY_VERSION

    assert await async_migrate_entry(hass, entry)

    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_future_entry_fails_without_downgrading() -> None:
    """Entries from a newer schema are not modified."""

    hass = MagicMock()
    entry = MagicMock()
    entry.options = {}
    entry.version = const.CONFIG_ENTRY_VERSION + 1

    assert not await async_migrate_entry(hass, entry)

    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_tilt_open_to_cover_open_delay_from_minutes_to_seconds() -> None:
    """Legacy minute values should be converted exactly once."""

    hass = MagicMock()
    entry = MagicMock()
    entry.options = {ConfKeys.TILT_OPEN_TO_COVER_OPEN_DELAY.value: 2}

    await _async_migrate_tilt_delays_to_seconds(hass, entry)

    updated_options = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert updated_options[ConfKeys.TILT_OPEN_TO_COVER_OPEN_DELAY.value] == 120
    assert updated_options[const.OPTION_KEY_TILT_DELAYS_IN_SECONDS] is True

    entry.options = updated_options
    await _async_migrate_tilt_delays_to_seconds(hass, entry)

    hass.config_entries.async_update_entry.assert_called_once()
