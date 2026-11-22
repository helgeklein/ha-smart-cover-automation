"""Tests for the optional earliest and latest time of evening closure and morning opening.

In the sun-relative modes (before/after sunset or sunrise), an optional earliest
and latest time of day limit the calculated time: the covers close or open no
earlier than the earliest and no later than the latest time. If both conflict,
the latest time takes precedence. Fixed-time and external modes are unaffected.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.automation_engine import AutomationEngine
from custom_components.smart_cover_automation.config import ConfKeys, resolve
from custom_components.smart_cover_automation.const import EveningClosureControl

TARGET_DATE = date(2025, 6, 21)
ASTRAL_PATH = "custom_components.smart_cover_automation.automation_engine.get_astral_event_date"


def _local(hour: int, minute: int) -> datetime:
    """Return a local datetime on the target date."""

    return datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, minute, tzinfo=dt_util.get_default_time_zone())


def _make_engine(mock_logger: MagicMock, options: dict[ConfKeys, Any]) -> AutomationEngine:
    """Create an engine for one cover with evening closure configured and the given options."""

    config: dict[str, Any] = {
        ConfKeys.COVERS.value: ["cover.test"],
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        ConfKeys.EVENING_CLOSURE.value: EveningClosureControl.CLOSE_AND_KEEP_CLOSED,
        ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
    }
    config.update({key.value: value for key, value in options.items()})
    return AutomationEngine(resolved=resolve(config), config=config, ha_interface=MagicMock(), logger=mock_logger)


@pytest.fixture
def frozen_today(freezer):
    """Freeze "now" on the target date so local datetimes are built for it."""

    freezer.move_to(_local(12, 0))


def test_time_limits_default_to_disabled() -> None:
    """The time limits are off by default, so existing installations behave as before."""

    resolved = resolve({})

    assert resolved.evening_closure_earliest_enabled is False
    assert resolved.evening_closure_latest_enabled is False
    assert resolved.morning_opening_earliest_enabled is False
    assert resolved.morning_opening_latest_enabled is False


class TestEveningClosureLatestTime:
    """Latest time for evening closure."""

    @pytest.mark.usefixtures("frozen_today")
    @pytest.mark.parametrize(
        ("mode", "sunset", "latest_enabled", "expected"),
        [
            # After sunset + 15 min: 21:45 + 0:15 = 22:00, capped at 21:30
            (const.EveningClosureMode.AFTER_SUNSET, (21, 45), True, (21, 30)),
            # Cap later than the calculated time: no change
            (const.EveningClosureMode.AFTER_SUNSET, (17, 0), True, (17, 15)),
            # Limit disabled: no cap
            (const.EveningClosureMode.AFTER_SUNSET, (21, 45), False, (22, 0)),
            # Before sunset - 15 min: 21:55 - 0:15 = 21:40, capped at 21:30
            (const.EveningClosureMode.BEFORE_SUNSET, (21, 55), True, (21, 30)),
        ],
    )
    def test_sunset_relative_time_is_capped(
        self, mock_logger, mode: const.EveningClosureMode, sunset: tuple[int, int], latest_enabled: bool, expected: tuple[int, int]
    ) -> None:
        """The sunset-relative closing time is capped at the latest time when enabled."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: mode.value,
                ConfKeys.EVENING_CLOSURE_TIME: "00:15:00",
                ConfKeys.EVENING_CLOSURE_LATEST_ENABLED: latest_enabled,
                ConfKeys.EVENING_CLOSURE_LATEST_TIME: "21:30:00",
            },
        )

        with patch(ASTRAL_PATH, return_value=_local(*sunset)):
            assert engine._get_evening_closure_time_for_date(TARGET_DATE) == _local(*expected)

    @pytest.mark.usefixtures("frozen_today")
    def test_fixed_time_is_not_capped(self, mock_logger) -> None:
        """The latest time doesn't apply to the fixed-time mode."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.FIXED_TIME.value,
                ConfKeys.EVENING_CLOSURE_TIME: "23:00:00",
                ConfKeys.EVENING_CLOSURE_LATEST_ENABLED: True,
                ConfKeys.EVENING_CLOSURE_LATEST_TIME: "21:30:00",
            },
        )

        assert engine._get_evening_closure_time_for_date(TARGET_DATE) == _local(23, 0)


class TestMorningOpeningLatestTime:
    """Latest time for morning opening."""

    @pytest.mark.usefixtures("frozen_today")
    @pytest.mark.parametrize(
        ("mode", "sunrise", "latest_enabled", "expected"),
        [
            # Winter: after sunrise + 0:30 = 8:45, capped at 7:30
            (const.MorningOpeningMode.AFTER_SUNRISE, (8, 15), True, (7, 30)),
            # Summer: 5:10 + 0:30 = 5:40, earlier than the cap: no change
            (const.MorningOpeningMode.AFTER_SUNRISE, (5, 10), True, (5, 40)),
            # Limit disabled: no cap
            (const.MorningOpeningMode.AFTER_SUNRISE, (8, 15), False, (8, 45)),
            # Before sunrise - 0:30: 8:15 - 0:30 = 7:45, capped at 7:30
            (const.MorningOpeningMode.BEFORE_SUNRISE, (8, 15), True, (7, 30)),
        ],
    )
    def test_sunrise_relative_time_is_capped(
        self, mock_logger, mode: const.MorningOpeningMode, sunrise: tuple[int, int], latest_enabled: bool, expected: tuple[int, int]
    ) -> None:
        """The sunrise-relative opening time is capped at the latest time when enabled."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.MORNING_OPENING_MODE: mode.value,
                ConfKeys.MORNING_OPENING_TIME: "00:30:00",
                ConfKeys.MORNING_OPENING_LATEST_ENABLED: latest_enabled,
                ConfKeys.MORNING_OPENING_LATEST_TIME: "07:30:00",
            },
        )

        with patch(ASTRAL_PATH, return_value=_local(*sunrise)):
            assert engine._get_morning_opening_time_for_date(TARGET_DATE) == _local(*expected)

    @pytest.mark.usefixtures("frozen_today")
    def test_fixed_time_is_not_capped(self, mock_logger) -> None:
        """The latest time doesn't apply to the fixed-time mode."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.MORNING_OPENING_MODE: const.MorningOpeningMode.FIXED_TIME.value,
                ConfKeys.MORNING_OPENING_TIME: "09:00:00",
                ConfKeys.MORNING_OPENING_LATEST_ENABLED: True,
                ConfKeys.MORNING_OPENING_LATEST_TIME: "07:30:00",
            },
        )

        assert engine._get_morning_opening_time_for_date(TARGET_DATE) == _local(9, 0)

    @pytest.mark.usefixtures("frozen_today")
    def test_capped_time_before_sunrise_enables_pre_sunrise_opening(self, mock_logger, freezer) -> None:
        """A capped opening time before sunrise counts as pre-sunrise opening, so covers may open in the dark."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.MORNING_OPENING_MODE: const.MorningOpeningMode.AFTER_SUNRISE.value,
                ConfKeys.MORNING_OPENING_TIME: "00:00:00",
                ConfKeys.MORNING_OPENING_LATEST_ENABLED: True,
                ConfKeys.MORNING_OPENING_LATEST_TIME: "07:30:00",
            },
        )
        freezer.move_to(_local(7, 45))

        with patch(ASTRAL_PATH, return_value=_local(8, 15)):
            assert engine._is_pre_sunrise_morning_opening_active() is True


class TestEveningClosureEarliestTime:
    """Earliest time for evening closure."""

    @pytest.mark.usefixtures("frozen_today")
    @pytest.mark.parametrize(
        ("sunset", "earliest_enabled", "expected"),
        [
            # Winter: 16:30 + 0:15 = 16:45, raised to 18:00
            ((16, 30), True, (18, 0)),
            # Summer: 21:45 + 0:15 = 22:00, later than the earliest time: no change
            ((21, 45), True, (22, 0)),
            # Limit disabled: no change
            ((16, 30), False, (16, 45)),
        ],
    )
    def test_sunset_relative_time_is_raised(
        self, mock_logger, sunset: tuple[int, int], earliest_enabled: bool, expected: tuple[int, int]
    ) -> None:
        """The sunset-relative closing time is raised to the earliest time when enabled."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.AFTER_SUNSET.value,
                ConfKeys.EVENING_CLOSURE_TIME: "00:15:00",
                ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED: earliest_enabled,
                ConfKeys.EVENING_CLOSURE_EARLIEST_TIME: "18:00:00",
            },
        )

        with patch(ASTRAL_PATH, return_value=_local(*sunset)):
            assert engine._get_evening_closure_time_for_date(TARGET_DATE) == _local(*expected)

    @pytest.mark.usefixtures("frozen_today")
    @pytest.mark.parametrize(
        ("sunset", "expected"),
        [
            # Winter: raised to the earliest time
            ((16, 30), (18, 0)),
            # Summer: capped at the latest time
            ((21, 45), (21, 30)),
            # In between: unchanged
            ((19, 0), (19, 15)),
        ],
    )
    def test_earliest_and_latest_combined(self, mock_logger, sunset: tuple[int, int], expected: tuple[int, int]) -> None:
        """With both limits enabled, the closing time stays within the window."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.AFTER_SUNSET.value,
                ConfKeys.EVENING_CLOSURE_TIME: "00:15:00",
                ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED: True,
                ConfKeys.EVENING_CLOSURE_EARLIEST_TIME: "18:00:00",
                ConfKeys.EVENING_CLOSURE_LATEST_ENABLED: True,
                ConfKeys.EVENING_CLOSURE_LATEST_TIME: "21:30:00",
            },
        )

        with patch(ASTRAL_PATH, return_value=_local(*sunset)):
            assert engine._get_evening_closure_time_for_date(TARGET_DATE) == _local(*expected)

    @pytest.mark.usefixtures("frozen_today")
    def test_fixed_time_is_not_raised(self, mock_logger) -> None:
        """The earliest time doesn't apply to the fixed-time mode."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.FIXED_TIME.value,
                ConfKeys.EVENING_CLOSURE_TIME: "17:00:00",
                ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED: True,
                ConfKeys.EVENING_CLOSURE_EARLIEST_TIME: "18:00:00",
            },
        )

        assert engine._get_evening_closure_time_for_date(TARGET_DATE) == _local(17, 0)


class TestMorningOpeningEarliestTime:
    """Earliest time for morning opening."""

    @pytest.mark.usefixtures("frozen_today")
    @pytest.mark.parametrize(
        ("mode", "sunrise", "earliest_enabled", "expected"),
        [
            # Summer: 5:10 + 0:00 = 5:10, raised to 7:00
            (const.MorningOpeningMode.AFTER_SUNRISE, (5, 10), True, (7, 0)),
            # Winter: 8:15, later than the earliest time: no change
            (const.MorningOpeningMode.AFTER_SUNRISE, (8, 15), True, (8, 15)),
            # Limit disabled: no change
            (const.MorningOpeningMode.AFTER_SUNRISE, (5, 10), False, (5, 10)),
            # Before sunrise: 5:10 - 0:00 = 5:10, raised to 7:00
            (const.MorningOpeningMode.BEFORE_SUNRISE, (5, 10), True, (7, 0)),
        ],
    )
    def test_sunrise_relative_time_is_raised(
        self, mock_logger, mode: const.MorningOpeningMode, sunrise: tuple[int, int], earliest_enabled: bool, expected: tuple[int, int]
    ) -> None:
        """The sunrise-relative opening time is raised to the earliest time when enabled."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.MORNING_OPENING_MODE: mode.value,
                ConfKeys.MORNING_OPENING_TIME: "00:00:00",
                ConfKeys.MORNING_OPENING_EARLIEST_ENABLED: earliest_enabled,
                ConfKeys.MORNING_OPENING_EARLIEST_TIME: "07:00:00",
            },
        )

        with patch(ASTRAL_PATH, return_value=_local(*sunrise)):
            assert engine._get_morning_opening_time_for_date(TARGET_DATE) == _local(*expected)

    @pytest.mark.usefixtures("frozen_today")
    def test_latest_takes_precedence_over_conflicting_earliest(self, mock_logger) -> None:
        """If the earliest time is later than the latest time, the latest time wins."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.MORNING_OPENING_MODE: const.MorningOpeningMode.AFTER_SUNRISE.value,
                ConfKeys.MORNING_OPENING_TIME: "00:00:00",
                ConfKeys.MORNING_OPENING_EARLIEST_ENABLED: True,
                ConfKeys.MORNING_OPENING_EARLIEST_TIME: "08:00:00",
                ConfKeys.MORNING_OPENING_LATEST_ENABLED: True,
                ConfKeys.MORNING_OPENING_LATEST_TIME: "07:30:00",
            },
        )

        with patch(ASTRAL_PATH, return_value=_local(6, 0)):
            assert engine._get_morning_opening_time_for_date(TARGET_DATE) == _local(7, 30)


class TestEveningClosureAroundMidnight:
    """Closing windows at or shortly before midnight."""

    @pytest.mark.usefixtures("frozen_today")
    def test_latest_time_midnight_means_end_of_evening(self, mock_logger) -> None:
        """A latest time of 00:00 caps the closing time at the end of the evening, not at the start of the day."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.AFTER_SUNSET.value,
                # 21:45 + 3:00 = 00:45 the next day, capped at midnight
                ConfKeys.EVENING_CLOSURE_TIME: "03:00:00",
                ConfKeys.EVENING_CLOSURE_LATEST_ENABLED: True,
                ConfKeys.EVENING_CLOSURE_LATEST_TIME: "00:00:00",
            },
        )

        with patch(ASTRAL_PATH, return_value=_local(21, 45)):
            closing = engine._get_evening_closure_time_for_date(TARGET_DATE)

        assert closing == _local(0, 0) + timedelta(days=1)

    @pytest.mark.parametrize(
        ("now", "expected"),
        [
            # Before the window
            ((23, 50), False),
            # Inside the window, before midnight
            ((23, 59), True),
            # Inside the window, after midnight: yesterday's window must still be found
            ((0, 3), True),
            # After the window
            ((0, 10), False),
        ],
    )
    def test_closing_window_crossing_midnight_is_not_missed(self, mock_logger, freezer, now: tuple[int, int], expected: bool) -> None:
        """A closing window starting shortly before midnight still triggers after midnight."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.FIXED_TIME.value,
                ConfKeys.EVENING_CLOSURE_TIME: "23:58:00",
            },
        )
        now_datetime = _local(*now) + (timedelta(days=1) if now[0] < 12 else timedelta())
        freezer.move_to(now_datetime)

        assert engine._check_evening_closure() is expected


class TestDstRollback:
    """Times in the repeated hour of a DST rollback resolve to a stable instant."""

    # Europe/Berlin falls back from 03:00 CEST to 02:00 CET on this date; 02:00-03:00 happens twice
    ROLLBACK_DATE = date(2026, 10, 25)

    @pytest.fixture
    def berlin_time_zone(self):
        """Use Europe/Berlin as the local time zone."""

        previous = dt_util.get_default_time_zone()
        dt_util.set_default_time_zone(ZoneInfo("Europe/Berlin"))
        yield
        dt_util.set_default_time_zone(previous)

    @pytest.mark.usefixtures("berlin_time_zone")
    @pytest.mark.parametrize(
        "now_utc",
        [
            # 02:10 CEST, first occurrence of the repeated hour
            datetime(2026, 10, 25, 0, 10, tzinfo=timezone.utc),
            # 02:10 CET, second occurrence of the repeated hour
            datetime(2026, 10, 25, 1, 10, tzinfo=timezone.utc),
            # Outside the repeated hour
            datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc),
        ],
    )
    def test_ambiguous_time_resolves_to_first_occurrence(self, mock_logger, freezer, now_utc: datetime) -> None:
        """An ambiguous local time doesn't move depending on the current time."""

        engine = _make_engine(mock_logger, {})
        freezer.move_to(now_utc)

        result = engine._get_local_datetime_for_date(self.ROLLBACK_DATE, datetime.strptime("02:30", "%H:%M").time())

        # 02:30 CEST = 00:30 UTC
        assert result == datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)

    @pytest.mark.usefixtures("berlin_time_zone")
    def test_morning_block_does_not_reactivate_in_repeated_hour(self, mock_logger, freezer) -> None:
        """Once the morning opening time has passed, the repeated hour doesn't block reopening again."""

        engine = _make_engine(
            mock_logger,
            {
                ConfKeys.EVENING_CLOSURE_MODE: const.EveningClosureMode.FIXED_TIME.value,
                ConfKeys.EVENING_CLOSURE_TIME: "20:00:00",
                ConfKeys.MORNING_OPENING_MODE: const.MorningOpeningMode.FIXED_TIME.value,
                ConfKeys.MORNING_OPENING_TIME: "02:30:00",
            },
        )

        # 02:10 CEST: before the morning opening time (02:30 CEST)
        freezer.move_to(datetime(2026, 10, 25, 0, 10, tzinfo=timezone.utc))
        assert engine._compute_post_evening_closure() is True

        # 02:10 CET: one hour later, the morning opening time has passed
        freezer.move_to(datetime(2026, 10, 25, 1, 10, tzinfo=timezone.utc))
        assert engine._compute_post_evening_closure() is False
