"""Tests for tilt-delay configuration migrations."""

from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation import _async_migrate_tilt_delays_to_seconds, const
from custom_components.smart_cover_automation.config import ConfKeys


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
