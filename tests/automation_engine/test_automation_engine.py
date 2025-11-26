"""Unit tests for the AutomationEngine class.

This module tests the AutomationEngine in isolation, focusing on:
- Initialization and configuration
- Sensor data gathering
- Global condition checking
- Main run logic
- Error handling
"""

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.automation_engine import AutomationEngine
from custom_components.smart_cover_automation.config import ConfKeys, resolve
from custom_components.smart_cover_automation.cover_automation import SensorData


@pytest.fixture
def mock_ha_interface():
    """Create a mock Home Assistant interface."""
    ha_interface = MagicMock()
    ha_interface.get_sun_data = MagicMock(return_value=(180.0, 45.0))
    ha_interface.get_max_temperature = AsyncMock(return_value=25.0)
    ha_interface.get_weather_condition = MagicMock(return_value="sunny")
    ha_interface.get_sun_state = MagicMock(return_value="above_horizon")
    return ha_interface


@pytest.fixture
def basic_config():
    """Create a basic test configuration."""
    return {
        ConfKeys.COVERS.value: ["cover.test"],
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        ConfKeys.TEMP_THRESHOLD.value: 20.0,
    }


@pytest.fixture
def automation_engine(mock_ha_interface, basic_config):
    """Create an AutomationEngine instance for testing."""
    resolved = resolve(basic_config)
    return AutomationEngine(
        resolved=resolved,
        config=basic_config,
        ha_interface=mock_ha_interface,
    )


class TestAutomationEngineInitialization:
    """Test AutomationEngine initialization."""

    def test_initialization_with_valid_config(self, automation_engine, basic_config):
        """Test that engine initializes correctly with valid configuration."""
        assert automation_engine.resolved is not None
        assert automation_engine.config == basic_config
        assert automation_engine._ha_interface is not None
        assert automation_engine._cover_pos_history_mgr is not None

    def test_initialization_stores_resolved_config(self, mock_ha_interface):
        """Test that resolved configuration is stored correctly."""
        config = {
            ConfKeys.COVERS.value: ["cover.living_room", "cover.bedroom"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.home",
            ConfKeys.TEMP_THRESHOLD.value: 25.0,
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        assert engine.resolved.temp_threshold == 25.0
        assert len(engine.resolved.covers) == 2
        assert "cover.living_room" in engine.resolved.covers


class TestGatherSensorData:
    """Test _gather_sensor_data method."""

    async def test_gather_sensor_data_success(self, automation_engine, mock_ha_interface):
        """Test successful sensor data gathering."""
        # Configure mocks
        mock_ha_interface.get_sun_data.return_value = (180.0, 45.0)
        mock_ha_interface.get_max_temperature.return_value = 28.0
        mock_ha_interface.get_weather_condition.return_value = "sunny"

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify results
        assert sensor_data is not None
        assert isinstance(sensor_data, SensorData)
        assert sensor_data.sun_azimuth == 180.0
        assert sensor_data.sun_elevation == 45.0
        assert sensor_data.temp_max == 28.0
        assert sensor_data.temp_hot is True  # 28.0 > 20.0 threshold
        assert sensor_data.weather_condition == "sunny"
        assert sensor_data.weather_sunny is True
        assert message == ""

    async def test_gather_sensor_data_temp_not_hot(self, automation_engine, mock_ha_interface):
        """Test sensor data when temperature is below threshold."""
        # Configure mocks
        mock_ha_interface.get_max_temperature.return_value = 15.0

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify results
        assert sensor_data is not None
        assert sensor_data.temp_hot is False  # 15.0 < 20.0 threshold

    async def test_gather_sensor_data_weather_not_sunny(self, automation_engine, mock_ha_interface):
        """Test sensor data with non-sunny weather."""
        # Configure mocks
        mock_ha_interface.get_weather_condition.return_value = "cloudy"

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify results
        assert sensor_data is not None
        assert sensor_data.weather_sunny is False

    async def test_gather_sensor_data_sun_unavailable(self, automation_engine, mock_ha_interface):
        """Test handling of unavailable sun data."""
        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        # Configure mock to raise error
        mock_ha_interface.get_sun_data.side_effect = InvalidSensorReadingError("sun.sun", "unavailable")

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify error handling
        assert sensor_data is None
        assert "sun.sun" in message or "unavailable" in message

    async def test_gather_sensor_data_weather_unavailable(self, automation_engine, mock_ha_interface):
        """Test handling of unavailable weather data."""
        from custom_components.smart_cover_automation.ha_interface import WeatherEntityNotFoundError

        # Configure mock to raise error
        mock_ha_interface.get_max_temperature.side_effect = WeatherEntityNotFoundError("Weather entity not found")

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify error handling
        assert sensor_data is None
        assert "Weather data unavailable" in message

    async def test_gather_sensor_data_sun_not_found_error_propagates(self, automation_engine, mock_ha_interface):
        """Test that SunSensorNotFoundError propagates as expected."""
        from custom_components.smart_cover_automation.coordinator import SunSensorNotFoundError

        # Configure mock to raise error
        mock_ha_interface.get_sun_data.side_effect = SunSensorNotFoundError("Sun sensor not found")

        # Verify error propagates
        with pytest.raises(SunSensorNotFoundError):
            await automation_engine._gather_sensor_data()

    async def test_gather_sensor_data_unexpected_sun_error(self, automation_engine, mock_ha_interface):
        """Test handling of unexpected errors when getting sun data."""
        # Configure mock to raise unexpected error
        mock_ha_interface.get_sun_data.side_effect = RuntimeError("Unexpected error")

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify error handling
        assert sensor_data is None
        assert "Unexpected error getting sun data" in message

    async def test_gather_sensor_data_unexpected_weather_error(self, automation_engine, mock_ha_interface):
        """Test handling of unexpected errors when getting weather data."""
        # Configure mock to raise unexpected error
        mock_ha_interface.get_max_temperature.side_effect = RuntimeError("Unexpected weather error")

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify error handling
        assert sensor_data is None
        assert "Unexpected error getting weather data" in message


class TestCheckGlobalConditions:
    """Test _check_global_conditions method."""

    def test_check_global_conditions_normal(self, automation_engine, mock_ha_interface):
        """Test global conditions check when everything is normal."""
        # Configure mocks
        mock_ha_interface.get_sun_state.return_value = "above_horizon"

        # Call method
        should_proceed, message, severity = automation_engine._check_global_conditions()

        # Verify results
        assert should_proceed is True
        assert message == ""

    def test_check_global_conditions_time_period_disabled(self, mock_ha_interface):
        """Test global conditions check when in disabled time period."""
        # Configure with disabled time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        # Mock current time to be within disabled period
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(23, 0)
            mock_now.return_value = mock_datetime

            # Call method
            should_proceed, message, severity = engine._check_global_conditions()

            # Verify results
            assert should_proceed is False
            assert "disabled for the current time period" in message
            assert "22:00:00 - 06:00:00" in message
            assert severity == const.LogSeverity.DEBUG


class TestInTimePeriodAutomationDisabled:
    """Test _in_time_period_automation_disabled method."""

    def test_time_period_disabled_not_configured(self, automation_engine):
        """Test when time period disabling is not configured."""
        # Call method
        is_disabled, period_string = automation_engine._in_time_period_automation_disabled()

        # Verify results
        assert is_disabled is False
        assert period_string == ""

    def test_time_period_disabled_outside_range(self, mock_ha_interface):
        """Test when current time is outside disabled range."""
        # Configure with disabled time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        # Mock current time to be outside disabled period
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(12, 0)  # Noon - outside 22:00-06:00 range
            mock_now.return_value = mock_datetime

            # Call method
            is_disabled, period_string = engine._in_time_period_automation_disabled()

            # Verify results
            assert is_disabled is False
            assert period_string == ""

    def test_time_period_disabled_inside_overnight_range(self, mock_ha_interface):
        """Test when current time is inside overnight disabled range."""
        # Configure with disabled time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        # Mock current time to be inside disabled period (late night)
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(23, 30)
            mock_now.return_value = mock_datetime

            # Call method
            is_disabled, period_string = engine._in_time_period_automation_disabled()

            # Verify results
            assert is_disabled is True
            assert period_string == "22:00:00 - 06:00:00"

    def test_time_period_disabled_inside_same_day_range(self, mock_ha_interface):
        """Test when current time is inside same-day disabled range."""
        # Configure with disabled time range
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(9, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(17, 0),
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        # Mock current time to be inside disabled period
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(13, 0)  # 1 PM - inside 09:00-17:00 range
            mock_now.return_value = mock_datetime

            # Call method
            is_disabled, period_string = engine._in_time_period_automation_disabled()

            # Verify results
            assert is_disabled is True
            assert period_string == "09:00:00 - 17:00:00"


class TestRunMethod:
    """Test the main run method."""

    async def test_run_with_no_covers_configured(self, mock_ha_interface):
        """Test run when no covers are configured."""
        # Configure with no covers
        config = {
            ConfKeys.COVERS.value: [],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        # Call run
        result = await engine.run({})

        # Verify result
        assert result[ConfKeys.COVERS.value] == {}

    async def test_run_with_automation_disabled(self, mock_ha_interface):
        """Test run when automation is disabled."""
        # Configure with automation disabled
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.ENABLED.value: False,
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        # Call run
        cover_states = {"cover.test": MagicMock()}
        result = await engine.run(cover_states)  # type: ignore[arg-type]

        # Verify result
        assert result[ConfKeys.COVERS.value] == {}

    async def test_run_with_all_covers_unavailable(self, automation_engine):
        """Test run when all covers are unavailable."""
        # Call run with all covers unavailable
        cover_states = {"cover.test": None}
        result = await automation_engine.run(cover_states)

        # Verify result
        assert result[ConfKeys.COVERS.value] == {}

    async def test_run_with_sensor_data_unavailable(self, automation_engine, mock_ha_interface):
        """Test run when sensor data is unavailable."""
        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        # Configure mock to return error
        mock_ha_interface.get_sun_data.side_effect = InvalidSensorReadingError("sun.sun", "unavailable")

        # Call run
        cover_states = {"cover.test": MagicMock()}
        result = await automation_engine.run(cover_states)  # type: ignore[arg-type]

        # Verify result
        assert result[ConfKeys.COVERS.value] == {}

    async def test_run_stores_sensor_data_in_result(self, automation_engine, mock_ha_interface):
        """Test that sensor data is stored in the result."""
        # Configure mocks
        mock_ha_interface.get_sun_data.return_value = (180.0, 45.0)
        mock_ha_interface.get_max_temperature.return_value = 25.0
        mock_ha_interface.get_weather_condition.return_value = "sunny"

        # Call run
        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {}
        cover_states = {"cover.test": cover_state}
        result = await automation_engine.run(cover_states)  # type: ignore[arg-type]

        # Verify sensor data in result
        assert "sun_azimuth" in result
        assert result["sun_azimuth"] == 180.0
        assert "sun_elevation" in result
        assert result["sun_elevation"] == 45.0
        assert "temp_current_max" in result
        assert result["temp_current_max"] == 25.0
        assert "temp_hot" in result
        assert "weather_sunny" in result

    async def test_run_blocked_by_nighttime(self, mock_ha_interface):
        """Test run when blocked by nighttime condition."""
        # Configure to block at night
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
        )

        # Configure mocks - sun is below horizon
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        # Call run
        cover_state = MagicMock()
        cover_states = {"cover.test": cover_state}
        result = await engine.run(cover_states)  # type: ignore[arg-type]

        # Verify automation was blocked but covers still appear with lock data
        assert "cover.test" in result[ConfKeys.COVERS.value]
        cover_data = result[ConfKeys.COVERS.value]["cover.test"]
        # Cover should only have lock data, no automation actions taken
        assert "cover_lock_mode" in cover_data
        assert "cover_lock_active" in cover_data


class TestLogAutomationResult:
    """Test _log_automation_result method."""

    def test_log_debug_message(self, automation_engine):
        """Test logging a debug message."""
        # This just verifies the method runs without error
        automation_engine._log_automation_result("Test debug message", const.LogSeverity.DEBUG)

    def test_log_info_message(self, automation_engine):
        """Test logging an info message."""
        automation_engine._log_automation_result("Test info message", const.LogSeverity.INFO)

    def test_log_warning_message(self, automation_engine):
        """Test logging a warning message."""
        automation_engine._log_automation_result("Test warning message", const.LogSeverity.WARNING)

    def test_log_error_message(self, automation_engine):
        """Test logging an error message."""
        automation_engine._log_automation_result("Test error message", const.LogSeverity.ERROR)


class TestCheckSunsetClosing:
    """Test _check_sunset_closing method for evening closure feature."""

    #
    # test_check_sunset_closing_feature_disabled
    #
    def test_check_sunset_closing_feature_disabled(self, mock_ha_interface):
        """Test that method returns False when feature is disabled."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: False,
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface)

        result = engine._check_sunset_closing()

        assert result is False
        # is_sunset should not be called when feature is disabled
        mock_ha_interface.is_sunset.assert_not_called()

    #
    # test_check_sunset_closing_sunset_detected_schedules_closing
    #
    @patch("custom_components.smart_cover_automation.automation_engine.datetime")
    def test_check_sunset_closing_sunset_detected_schedules_closing(self, mock_datetime, mock_ha_interface):
        """Test that sunset detection schedules cover closing after delay."""
        from datetime import datetime as real_datetime
        from datetime import timedelta, timezone

        # Setup: feature enabled with 15 minute delay
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 15, "seconds": 0},
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface)

        # Mock current time
        fake_now = real_datetime(2025, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fake_now
        mock_datetime.side_effect = lambda *args, **kw: real_datetime(*args, **kw)

        # Mock sunset detection
        mock_ha_interface.is_sunset.return_value = True
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        # Call method
        result = engine._check_sunset_closing()

        # Should not return True yet (just scheduled)
        assert result is False

        # Verify scheduled time was set (15 minutes = 900 seconds later)
        expected_time = fake_now + timedelta(seconds=900)
        assert engine._sunset_close_scheduled_at == expected_time
        assert engine._sunset_covers_closed is False

    #
    # test_check_sunset_closing_time_reached_returns_true_once
    #
    @patch("custom_components.smart_cover_automation.automation_engine.datetime")
    def test_check_sunset_closing_time_reached_returns_true_once(self, mock_datetime, mock_ha_interface):
        """Test that method returns True once when scheduled time is reached."""
        from datetime import datetime as real_datetime
        from datetime import timedelta, timezone

        # Setup
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 15, "seconds": 0},
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface)

        # Pre-schedule a closing time in the past
        fake_now = real_datetime(2025, 11, 4, 18, 45, 0, tzinfo=timezone.utc)
        scheduled_time = fake_now - timedelta(minutes=5)  # 5 minutes ago
        engine._sunset_close_scheduled_at = scheduled_time
        engine._sunset_covers_closed = False

        mock_datetime.now.return_value = fake_now
        mock_datetime.side_effect = lambda *args, **kw: real_datetime(*args, **kw)
        mock_ha_interface.is_sunset.return_value = False
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        # First call: should return True
        result = engine._check_sunset_closing()
        assert result is True
        assert engine._sunset_covers_closed is True

        # Second call: should return False (already closed)
        result = engine._check_sunset_closing()
        assert result is False

        # Third call: should still return False
        result = engine._check_sunset_closing()
        assert result is False

    #
    # test_check_sunset_closing_not_yet_time
    #
    @patch("custom_components.smart_cover_automation.automation_engine.datetime")
    def test_check_sunset_closing_not_yet_time(self, mock_datetime, mock_ha_interface):
        """Test that method returns False when scheduled time hasn't arrived yet."""
        from datetime import datetime as real_datetime
        from datetime import timedelta, timezone

        # Setup
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 15, "seconds": 0},
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface)

        # Schedule closing time in the future
        fake_now = real_datetime(2025, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        scheduled_time = fake_now + timedelta(minutes=10)  # 10 minutes from now
        engine._sunset_close_scheduled_at = scheduled_time
        engine._sunset_covers_closed = False

        mock_datetime.now.return_value = fake_now
        mock_datetime.side_effect = lambda *args, **kw: real_datetime(*args, **kw)
        mock_ha_interface.is_sunset.return_value = False
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        # Should return False (not time yet)
        result = engine._check_sunset_closing()
        assert result is False
        assert engine._sunset_covers_closed is False

    #
    # test_check_sunset_closing_resets_at_sunrise
    #
    @patch("custom_components.smart_cover_automation.automation_engine.datetime")
    def test_check_sunset_closing_resets_at_sunrise(self, mock_datetime, mock_ha_interface):
        """Test that state resets when sun goes above horizon."""
        from datetime import datetime as real_datetime
        from datetime import timezone

        # Setup with already closed state
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 15, "seconds": 0},
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface)

        # Set state to "already closed after sunset"
        fake_now = real_datetime(2025, 11, 4, 19, 0, 0, tzinfo=timezone.utc)
        engine._sunset_close_scheduled_at = fake_now
        engine._sunset_covers_closed = True

        mock_datetime.now.return_value = fake_now
        mock_datetime.side_effect = lambda *args, **kw: real_datetime(*args, **kw)
        mock_ha_interface.is_sunset.return_value = False

        # Sun goes above horizon (sunrise)
        mock_ha_interface.get_sun_state.return_value = "above_horizon"

        # Call method
        result = engine._check_sunset_closing()

        # Should reset state
        assert result is False
        assert engine._sunset_close_scheduled_at is None
        assert engine._sunset_covers_closed is False

    #
    # test_check_sunset_closing_multiple_sunset_cycles
    #
    @patch("custom_components.smart_cover_automation.automation_engine.datetime")
    def test_check_sunset_closing_multiple_sunset_cycles(self, mock_datetime, mock_ha_interface):
        """Test that feature works correctly across multiple day/night cycles."""
        from datetime import datetime as real_datetime
        from datetime import timedelta, timezone

        # Setup
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 15, "seconds": 0},
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface)

        # Day 1: Sunset detected
        day1_sunset = real_datetime(2025, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = day1_sunset
        mock_datetime.side_effect = lambda *args, **kw: real_datetime(*args, **kw)
        mock_ha_interface.is_sunset.return_value = True
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        result = engine._check_sunset_closing()
        assert result is False  # Just scheduled

        # Day 1: Time reached
        day1_close_time = day1_sunset + timedelta(minutes=15)
        mock_datetime.now.return_value = day1_close_time
        mock_ha_interface.is_sunset.return_value = False

        result = engine._check_sunset_closing()
        assert result is True  # First closing
        assert engine._sunset_covers_closed is True

        # Day 2: Sunrise resets
        day2_sunrise = day1_close_time + timedelta(hours=12)
        mock_datetime.now.return_value = day2_sunrise
        mock_ha_interface.get_sun_state.return_value = "above_horizon"

        result = engine._check_sunset_closing()
        assert result is False
        assert engine._sunset_close_scheduled_at is None
        assert engine._sunset_covers_closed is False

        # Day 2: Another sunset
        day2_sunset = day2_sunrise + timedelta(hours=8)
        mock_datetime.now.return_value = day2_sunset
        mock_ha_interface.is_sunset.return_value = True
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        result = engine._check_sunset_closing()
        assert result is False  # Scheduled again

        # Day 2: Time reached again
        day2_close_time = day2_sunset + timedelta(minutes=15)
        mock_datetime.now.return_value = day2_close_time
        mock_ha_interface.is_sunset.return_value = False

        result = engine._check_sunset_closing()
        assert result is True  # Second closing works!

    #
    # test_check_sunset_closing_zero_delay
    #
    @patch("custom_components.smart_cover_automation.automation_engine.datetime")
    def test_check_sunset_closing_zero_delay(self, mock_datetime, mock_ha_interface):
        """Test that zero delay triggers immediately on sunset."""
        from datetime import datetime as real_datetime
        from datetime import timezone

        # Setup with zero delay
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 0, "seconds": 0},
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface)

        # Mock time
        fake_now = real_datetime(2025, 11, 4, 18, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fake_now
        mock_datetime.side_effect = lambda *args, **kw: real_datetime(*args, **kw)

        # Sunset detected
        mock_ha_interface.is_sunset.return_value = True
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        # With zero delay, should trigger immediately when sunset detected
        result = engine._check_sunset_closing()
        assert result is True  # Triggers immediately with zero delay

        # Second call should return False (already closed)
        mock_ha_interface.is_sunset.return_value = False

        result = engine._check_sunset_closing()
        assert result is False
