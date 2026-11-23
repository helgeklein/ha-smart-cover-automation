"""Tests for the config entry v2 → v3 migration of the evening closure options.

In v3, the evening closure on/off switch and the "keep covers closed" switch were merged
into one evening closure setting (off / close once / close and keep closed).
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation import async_migrate_entry, const
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import EveningClosureControl

# Config entry schema version before the evening closure options were merged
CONFIG_ENTRY_VERSION_SEPARATE_EVENING_CLOSURE_OPTIONS = 2


#
# _migrate
#
async def _migrate(options: dict[str, Any]) -> dict[str, Any]:
    """Run the migration for a v2 entry with the given options and return the migrated options."""

    hass = MagicMock()
    entry = MagicMock()
    entry.options = options
    entry.version = CONFIG_ENTRY_VERSION_SEPARATE_EVENING_CLOSURE_OPTIONS

    assert await async_migrate_entry(hass, entry)

    update_kwargs = hass.config_entries.async_update_entry.call_args.kwargs
    assert update_kwargs["version"] == const.CONFIG_ENTRY_VERSION
    return update_kwargs["options"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("legacy_enabled", "legacy_keep_closed", "expected"),
    [
        (False, True, EveningClosureControl.OFF),
        (False, False, EveningClosureControl.OFF),
        (True, True, EveningClosureControl.CLOSE_AND_KEEP_CLOSED),
        (True, False, EveningClosureControl.CLOSE_ONCE),
        # "Keep covers closed" was on by default, so an unset value means keep closed
        (True, None, EveningClosureControl.CLOSE_AND_KEEP_CLOSED),
        (False, None, EveningClosureControl.OFF),
    ],
)
async def test_legacy_evening_closure_options_are_merged(legacy_enabled: bool, legacy_keep_closed: bool | None, expected: str) -> None:
    """The on/off and keep-closed values map to the evening closure setting; the legacy key is removed."""

    options: dict[str, Any] = {ConfKeys.EVENING_CLOSURE.value: legacy_enabled}
    if legacy_keep_closed is not None:
        options[const.LEGACY_OPTION_KEY_EVENING_CLOSURE_KEEP_CLOSED] = legacy_keep_closed

    migrated = await _migrate(options)

    assert migrated[ConfKeys.EVENING_CLOSURE.value] == expected
    assert const.LEGACY_OPTION_KEY_EVENING_CLOSURE_KEEP_CLOSED not in migrated


@pytest.mark.asyncio
async def test_unconfigured_evening_closure_keeps_default() -> None:
    """Entries that never configured evening closure keep using the default; a stray keep-closed value is dropped."""

    migrated = await _migrate({const.LEGACY_OPTION_KEY_EVENING_CLOSURE_KEEP_CLOSED: False})

    assert ConfKeys.EVENING_CLOSURE.value not in migrated
    assert const.LEGACY_OPTION_KEY_EVENING_CLOSURE_KEEP_CLOSED not in migrated


@pytest.mark.asyncio
async def test_v2_entry_keeps_daytime_movement_directions_default() -> None:
    """The v1 → v2 step is not applied to v2 entries."""

    migrated = await _migrate({})

    assert ConfKeys.DAYTIME_MOVEMENT_DIRECTIONS.value not in migrated
