"""Tests for the evening closure setting in AutomationEngine.

Covers the engine-level gates of the evening closure setting (closing window,
post-evening-closure block, pre-sunrise morning opening) for all its values, and the
end of the overnight block while the morning opening switch is off.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.automation_engine import AutomationEngine
from custom_components.smart_cover_automation.config import ConfKeys, resolve


def _make_engine(mock_ha_interface: MagicMock, mock_logger: MagicMock, **options: Any) -> AutomationEngine:
    """Create an engine for one cover with fixed-time evening closure at 20:00 and the given options."""

    config: dict[str, Any] = {
        ConfKeys.COVERS.value: ["cover.test"],
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        ConfKeys.EVENING_CLOSURE_MODE.value: const.EveningClosureMode.FIXED_TIME.value,
        ConfKeys.EVENING_CLOSURE_TIME.value: "20:00:00",
        ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        ConfKeys.MORNING_OPENING_MODE.value: const.MorningOpeningMode.FIXED_TIME.value,
        ConfKeys.MORNING_OPENING_TIME.value: "07:00:00",
    }
    config.update(options)
    return AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)


# Evening closure values and whether evening closure is on
EVENING_CLOSURE_VALUES = [
    (const.EveningClosureControl.OFF, False),
    (const.EveningClosureControl.CLOSE_ONCE, True),
    (const.EveningClosureControl.CLOSE_AND_KEEP_CLOSED, True),
]


class TestEveningClosureSetting:
    """Engine gates of the evening closure setting."""

    @pytest.mark.parametrize(("value", "expected"), EVENING_CLOSURE_VALUES)
    def test_check_evening_closure(self, mock_logger, freezer, value: str, expected: bool) -> None:
        """Covers are only signaled to close inside the window when evening closure is on."""

        engine = _make_engine(MagicMock(), mock_logger, **{ConfKeys.EVENING_CLOSURE.value: value})
        freezer.move_to(datetime(2025, 11, 4, 20, 5, 0, tzinfo=dt_util.get_default_time_zone()))

        assert engine._check_evening_closure() is expected

    @pytest.mark.parametrize(("value", "expected"), EVENING_CLOSURE_VALUES)
    def test_compute_post_evening_closure(self, mock_logger, freezer, value: str, expected: bool) -> None:
        """The overnight reopening block only applies when evening closure is on."""

        engine = _make_engine(MagicMock(), mock_logger, **{ConfKeys.EVENING_CLOSURE.value: value})
        freezer.move_to(datetime(2025, 11, 4, 22, 0, 0, tzinfo=dt_util.get_default_time_zone()))

        assert engine._compute_post_evening_closure() is expected

    def test_pre_sunrise_morning_opening_inactive_when_off(self, mock_logger) -> None:
        """Pre-sunrise morning opening is not evaluated while evening closure is off."""

        engine = _make_engine(MagicMock(), mock_logger, **{ConfKeys.EVENING_CLOSURE.value: const.EveningClosureControl.OFF})

        with patch.object(engine, "_get_morning_opening_time_for_date") as mock_morning_time:
            assert engine._is_pre_sunrise_morning_opening_active() is False

        mock_morning_time.assert_not_called()

    def test_switching_off_resets_closing_state(self, mock_logger, freezer) -> None:
        """Switching evening closure off right after a closure must not suppress the next day's closure.

        The setting can change at runtime without a reload, so the engine keeps its state.
        """

        engine = _make_engine(MagicMock(), mock_logger, **{ConfKeys.EVENING_CLOSURE.value: const.EveningClosureControl.CLOSE_ONCE})
        enabled = engine.resolved
        tz = dt_util.get_default_time_zone()

        # Monday: close in the window, then switch off before the window ends
        freezer.move_to(datetime(2025, 11, 3, 20, 2, 0, tzinfo=tz))
        assert engine._check_evening_closure() is True
        engine.resolved = dataclasses.replace(enabled, evening_closure=const.EveningClosureControl.OFF)
        freezer.tick(timedelta(minutes=3))
        assert engine._check_evening_closure() is False

        # Tuesday: switched on again inside the closing window
        engine.resolved = enabled
        freezer.move_to(datetime(2025, 11, 4, 20, 5, 0, tzinfo=tz))
        assert engine._check_evening_closure() is True


ASTRAL_PATH = "custom_components.smart_cover_automation.automation_engine.get_astral_event_date"


class TestOvernightBlockWithMorningOpeningOff:
    """End of the overnight reopening block when morning opening yields no time."""

    @staticmethod
    def _make_external_engine(mock_logger: MagicMock, *, morning_opening_enabled: bool) -> AutomationEngine:
        """Create an engine with external morning opening but no external time set."""

        return _make_engine(
            MagicMock(),
            mock_logger,
            **{
                ConfKeys.EVENING_CLOSURE.value: const.EveningClosureControl.CLOSE_ONCE,
                ConfKeys.MORNING_OPENING_ENABLED.value: morning_opening_enabled,
                ConfKeys.MORNING_OPENING_MODE.value: const.MorningOpeningMode.EXTERNAL.value,
            },
        )

    def test_off_ends_block_at_sunrise(self, mock_logger, freezer) -> None:
        """With morning opening off, a missing external time doesn't block covers released by a manual move all day."""

        tz = dt_util.get_default_time_zone()
        engine = self._make_external_engine(mock_logger, morning_opening_enabled=False)
        sunrise = datetime(2025, 11, 4, 7, 15, 0, tzinfo=tz)

        with patch(ASTRAL_PATH, return_value=sunrise):
            freezer.move_to(datetime(2025, 11, 4, 6, 0, 0, tzinfo=tz))
            assert engine._compute_post_evening_closure() is True
            freezer.move_to(datetime(2025, 11, 4, 12, 0, 0, tzinfo=tz))
            assert engine._compute_post_evening_closure() is False

    def test_on_keeps_block_until_external_time_is_set(self, mock_logger, freezer) -> None:
        """With morning opening on, a missing external time keeps the block active (unchanged behavior)."""

        tz = dt_util.get_default_time_zone()
        engine = self._make_external_engine(mock_logger, morning_opening_enabled=True)

        with patch(ASTRAL_PATH, return_value=datetime(2025, 11, 4, 7, 15, 0, tzinfo=tz)):
            freezer.move_to(datetime(2025, 11, 4, 12, 0, 0, tzinfo=tz))
            assert engine._compute_post_evening_closure() is True
