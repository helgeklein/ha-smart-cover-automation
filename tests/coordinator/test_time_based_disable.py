"""Tests for time-based automation disable functionality.

This module tests the coordinator methods that determine when the automation
should be disabled based on time periods and night/day conditions.
"""

from __future__ import annotations

from datetime import time
from unittest.mock import MagicMock, patch

import pytest

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys, resolve
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


class TestNighttimeAndLetLightInDisabled:
    """Test _nighttime_and_night_privacy method."""

    async def test_disabled_during_night_when_configured(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that automation is disabled at night when night_privacy is True."""
        # Configure to disable during night
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.NIGHT_PRIVACY.value: True,
        }
        resolved = resolve(config)

        # Create mock sun entity with state below horizon
        sun_entity = MagicMock()
        sun_entity.state = const.HA_SUN_STATE_BELOW_HORIZON

        # Test the method
        result = coordinator._nighttime_and_night_privacy(resolved, sun_entity)

        assert result is True

    async def test_not_disabled_during_night_when_not_configured(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that automation runs at night when night_privacy is False."""
        # Configure to NOT disable during night
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.NIGHT_PRIVACY.value: False,
        }
        resolved = resolve(config)

        # Create mock sun entity with state below horizon
        sun_entity = MagicMock()
        sun_entity.state = const.HA_SUN_STATE_BELOW_HORIZON

        # Test the method
        result = coordinator._nighttime_and_night_privacy(resolved, sun_entity)

        assert result is False

    async def test_not_disabled_during_day(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that automation runs during day regardless of configuration."""
        # Configure to disable during night
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.NIGHT_PRIVACY.value: True,
        }
        resolved = resolve(config)

        # Create mock sun entity with state above horizon
        sun_entity = MagicMock()
        sun_entity.state = "above_horizon"

        # Test the method
        result = coordinator._nighttime_and_night_privacy(resolved, sun_entity)

        assert result is False

    async def test_handles_missing_sun_entity(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that method handles None sun entity gracefully."""
        # Configure to disable during night
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.NIGHT_PRIVACY.value: True,
        }
        resolved = resolve(config)

        # Test with None sun entity
        result = coordinator._nighttime_and_night_privacy(resolved, None)  # type: ignore[arg-type]

        assert result is False


class TestInTimePeriodAutomationDisabled:
    """Test _in_time_period_automation_disabled method."""

    async def test_not_disabled_when_time_range_not_configured(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that automation runs when no time range is configured."""
        # Configure without time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: False,
        }
        resolved = resolve(config)

        # Test the method
        is_disabled, period_string = coordinator._in_time_period_automation_disabled(resolved)

        assert is_disabled is False
        assert period_string == ""

    @pytest.mark.parametrize(
        "current_time,start,end,expected_disabled,description",
        [
            # Same-day period (09:00 - 17:00)
            (time(8, 0), time(9, 0), time(17, 0), False, "before same-day period"),
            (time(9, 0), time(9, 0), time(17, 0), True, "at start of same-day period"),
            (time(13, 0), time(9, 0), time(17, 0), True, "during same-day period"),
            (time(16, 59), time(9, 0), time(17, 0), True, "just before end of same-day period"),
            (time(17, 0), time(9, 0), time(17, 0), False, "at end of same-day period"),
            (time(18, 0), time(9, 0), time(17, 0), False, "after same-day period"),
            # Overnight period (22:00 - 06:00)
            (time(21, 0), time(22, 0), time(6, 0), False, "before overnight period"),
            (time(22, 0), time(22, 0), time(6, 0), True, "at start of overnight period"),
            (time(23, 30), time(22, 0), time(6, 0), True, "late night during overnight period"),
            (time(0, 0), time(22, 0), time(6, 0), True, "midnight during overnight period"),
            (time(3, 0), time(22, 0), time(6, 0), True, "early morning during overnight period"),
            (time(5, 59), time(22, 0), time(6, 0), True, "just before end of overnight period"),
            (time(6, 0), time(22, 0), time(6, 0), False, "at end of overnight period"),
            (time(8, 0), time(22, 0), time(6, 0), False, "after overnight period"),
            # Edge cases
            (time(0, 0), time(0, 0), time(23, 59), True, "midnight at start of almost-full-day period"),
            (time(12, 0), time(0, 0), time(23, 59), True, "noon during almost-full-day period"),
            (time(23, 59), time(0, 0), time(23, 59), False, "at end time of almost-full-day period (excluded)"),
        ],
    )
    async def test_time_period_detection(
        self,
        coordinator: DataUpdateCoordinator,
        current_time: time,
        start: time,
        end: time,
        expected_disabled: bool,
        description: str,
    ) -> None:
        """Test time period detection with various time combinations."""
        # Configure with time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: start,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: end,
        }
        resolved = resolve(config)

        # Mock the current time
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = current_time
            mock_now.return_value = mock_datetime

            # Test the method
            is_disabled, period_string = coordinator._in_time_period_automation_disabled(resolved)

            assert is_disabled is expected_disabled, f"Failed: {description}"

            if expected_disabled:
                expected_string = f"{start.strftime('%H:%M:%S')} - {end.strftime('%H:%M:%S')}"
                assert period_string == expected_string
            else:
                assert period_string == ""

    async def test_period_string_format(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that the period string is properly formatted when in disabled period."""
        # Configure with time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 30, 15),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 45, 30),
        }
        resolved = resolve(config)

        # Mock the current time to be within the disabled period
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(23, 0)
            mock_now.return_value = mock_datetime

            # Test the method
            is_disabled, period_string = coordinator._in_time_period_automation_disabled(resolved)

            assert is_disabled is True
            assert period_string == "22:30:15 - 06:45:30"

    async def test_same_start_and_end_time(self, coordinator: DataUpdateCoordinator) -> None:
        """Test edge case where start and end times are the same."""
        # Configure with same start and end time (unusual but possible)
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(12, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(12, 0),
        }
        resolved = resolve(config)

        # Mock the current time
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(12, 0)
            mock_now.return_value = mock_datetime

            # Test the method - when start == end, it's treated as overnight (wrapping around)
            is_disabled, period_string = coordinator._in_time_period_automation_disabled(resolved)

            # At exactly 12:00 with start=12:00 and end=12:00, it should be disabled
            # because the check is: now_local >= period_start (12:00 >= 12:00 is True)
            assert is_disabled is True


class TestTimeBasedDisableIntegration:
    """Integration tests combining time-based disable methods with coordinator update."""

    async def test_coordinator_skips_during_night_when_configured(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that coordinator correctly detects nighttime for let light in disabled."""
        # Configure to disable during night
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.NIGHT_PRIVACY.value: True,
        }
        resolved = resolve(config)

        # Mock sun entity to be below horizon
        sun_state = MagicMock()
        sun_state.state = const.HA_SUN_STATE_BELOW_HORIZON

        # Test the method directly
        is_disabled = coordinator._nighttime_and_night_privacy(resolved, sun_state)

        # Verify that automation is correctly detected as disabled
        assert is_disabled is True

    async def test_coordinator_skips_during_disabled_time_period(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that coordinator correctly detects disabled time period."""
        # Set up configuration with time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        resolved = resolve(config)

        # Mock the current time to be within disabled period
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(23, 0)
            mock_now.return_value = mock_datetime

            # Test the method directly
            is_disabled, period_string = coordinator._in_time_period_automation_disabled(resolved)

            # Verify that automation is correctly detected as disabled
            assert is_disabled is True
            assert "22:00:00 - 06:00:00" in period_string
