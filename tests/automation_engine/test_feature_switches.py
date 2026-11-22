"""Tests for the evening closure setting in AutomationEngine.

Covers the engine-level gates of the evening closure setting (closing window,
post-evening-closure block, pre-sunrise morning opening) for all its values.
"""

from __future__ import annotations

from datetime import datetime
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
