"""Unit tests for the AutomationEngine class.

This module tests the AutomationEngine in isolation, focusing on:
- Initialization and configuration
- Sensor data gathering
- Global condition checking
- Main run logic
- Error handling
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.automation_engine import AutomationEngine, ScheduledCoverExecution
from custom_components.smart_cover_automation.config import ConfKeys, resolve
from custom_components.smart_cover_automation.cover_automation import (
    CoverExecutionPlan,
    CoverMovementReason,
    CoverState,
    SensorData,
)


@pytest.fixture
def mock_ha_interface():
    """Create a mock Home Assistant interface."""
    ha_interface = MagicMock()
    ha_interface.get_sun_data = MagicMock(return_value=(180.0, 45.0))
    ha_interface.get_daily_temperature_extrema = AsyncMock(return_value=(25.0, 18.0))
    ha_interface.get_weather_condition = MagicMock(return_value="sunny")
    ha_interface.get_sun_state = MagicMock(return_value="above_horizon")
    return ha_interface


@pytest.fixture
def basic_config():
    """Create a basic test configuration."""
    return {
        ConfKeys.COVERS.value: ["cover.test"],
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
        ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
    }


@pytest.fixture
def automation_engine(mock_ha_interface, basic_config, mock_logger):
    """Create an AutomationEngine instance for testing."""
    resolved = resolve(basic_config)
    return AutomationEngine(
        resolved=resolved,
        config=basic_config,
        ha_interface=mock_ha_interface,
        logger=mock_logger,
    )


class TestAutomationEngineInitialization:
    """Test AutomationEngine initialization."""

    def test_initialization_with_valid_config(self, automation_engine, basic_config):
        """Test that engine initializes correctly with valid configuration."""
        assert automation_engine.resolved is not None
        assert automation_engine.config == basic_config
        assert automation_engine._ha_interface is not None
        assert automation_engine._cover_pos_history_mgr is not None

    def test_initialization_stores_resolved_config(self, mock_ha_interface, mock_logger):
        """Test that resolved configuration is stored correctly."""
        config = {
            ConfKeys.COVERS.value: ["cover.living_room", "cover.bedroom"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.home",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 25.0,
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        assert engine.resolved.daily_max_temperature_threshold == 25.0
        assert len(engine.resolved.covers) == 2
        assert "cover.living_room" in engine.resolved.covers


class TestGatherSensorData:
    """Test _gather_sensor_data method."""

    async def test_gather_sensor_data_success(self, automation_engine, mock_ha_interface):
        """Test successful sensor data gathering."""
        # Configure mocks
        mock_ha_interface.get_sun_data.return_value = (180.0, 45.0)
        mock_ha_interface.get_daily_temperature_extrema.return_value = (28.0, 18.0)
        mock_ha_interface.get_weather_condition.return_value = "sunny"

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify results
        assert sensor_data is not None
        assert isinstance(sensor_data, SensorData)
        assert sensor_data.sun_azimuth == 180.0
        assert sensor_data.sun_elevation == 45.0
        assert sensor_data.temp_max == 28.0
        assert sensor_data.temp_min == 18.0
        assert sensor_data.temp_hot is True  # 28.0 > 20.0 threshold
        assert sensor_data.weather_condition == "sunny"
        assert sensor_data.weather_sunny is True
        assert message == ""

    async def test_gather_sensor_data_temp_hot_when_both_thresholds_equal(self, automation_engine, mock_ha_interface):
        """Test sensor data when both daily extrema equal the configured thresholds."""

        mock_ha_interface.get_daily_temperature_extrema.return_value = (20.0, 15.0)

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is True
        assert message == ""

    async def test_gather_sensor_data_temp_not_hot(self, automation_engine, mock_ha_interface):
        """Test sensor data when temperature is below threshold."""
        # Configure mocks
        mock_ha_interface.get_daily_temperature_extrema.return_value = (15.0, 16.0)

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify results
        assert sensor_data is not None
        assert sensor_data.temp_hot is False  # 15.0 < daily max threshold

    async def test_gather_sensor_data_daily_min_threshold_not_met(self, automation_engine, mock_ha_interface):
        """Test sensor data when the daily minimum temperature is below threshold."""

        mock_ha_interface.get_daily_temperature_extrema.return_value = (28.0, 10.0)

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is False
        assert message == ""

    async def test_gather_sensor_data_missing_daily_min_uses_daily_max_only(self, automation_engine, mock_ha_interface):
        """Test that a missing forecast low falls back to the daily max threshold."""

        mock_ha_interface.get_daily_temperature_extrema.return_value = (28.0, None)

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_min is None
        assert sensor_data.temp_hot is True
        assert message == ""

    async def test_gather_sensor_data_temp_not_hot_when_daily_min_below_equal_max(self, automation_engine, mock_ha_interface):
        """Test sensor data when max equals threshold but daily minimum stays below it."""

        mock_ha_interface.get_daily_temperature_extrema.return_value = (20.0, 14.5)

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is False
        assert message == ""

    async def test_gather_sensor_data_weather_not_sunny(self, automation_engine, mock_ha_interface):
        """Test sensor data with non-sunny weather."""
        # Configure mocks
        mock_ha_interface.get_weather_condition.return_value = "cloudy"

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify results
        assert sensor_data is not None
        assert sensor_data.weather_sunny is False

    async def test_gather_sensor_data_weather_hot_external_control_overrides_forecast(self, automation_engine, mock_ha_interface):
        """Test that external hot control overrides the forecast-derived temperature state."""
        mock_ha_interface.get_daily_temperature_extrema.return_value = (15.0, 16.0)
        automation_engine.config[const.SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL] = True

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is True
        assert message == ""

    async def test_gather_sensor_data_missing_weather_condition_without_cache_skips_sunshine_logic(
        self, automation_engine, mock_ha_interface
    ):
        """Missing weather condition without a cached fallback should keep sunshine-dependent logic unavailable."""

        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        mock_ha_interface.get_weather_condition.side_effect = InvalidSensorReadingError("weather.test", "condition missing")

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.weather_condition is None
        assert sensor_data.weather_sunny is None
        assert message == "Weather condition unavailable, skipping weather-dependent actions that require sunshine state"

    async def test_gather_sensor_data_weather_sunny_external_control_overrides_weather_entity(self, automation_engine, mock_ha_interface):
        """Test that external sunny control overrides the weather entity state."""
        mock_ha_interface.get_weather_condition.return_value = "cloudy"
        automation_engine.config[const.SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] = True

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.weather_sunny is True
        assert message == ""

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
        mock_ha_interface.get_daily_temperature_extrema.side_effect = WeatherEntityNotFoundError("Weather entity not found")

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify error handling
        assert sensor_data is not None
        assert sensor_data.temp_max is None
        assert sensor_data.temp_hot is None
        assert sensor_data.weather_sunny is True
        assert "Weather forecast unavailable" in message

    async def test_gather_sensor_data_weather_unavailable_uses_cached_values(self, automation_engine, mock_ha_interface):
        """Test offline weather fallback to last known values."""

        first_sensor_data, first_message = await automation_engine._gather_sensor_data()

        assert first_sensor_data is not None
        assert first_message == ""

        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        mock_ha_interface.get_daily_temperature_extrema.side_effect = InvalidSensorReadingError("weather.test", "Forecast unavailable")
        mock_ha_interface.get_weather_condition.side_effect = InvalidSensorReadingError("weather.test", "state is unavailable")

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_max == first_sensor_data.temp_max
        assert sensor_data.temp_min == first_sensor_data.temp_min
        assert sensor_data.temp_hot == first_sensor_data.temp_hot
        assert sensor_data.weather_condition == first_sensor_data.weather_condition

    async def test_gather_sensor_data_keeps_effective_daily_extrema_for_day(self, automation_engine, mock_ha_interface):
        """The stored daily max should not decrease and the stored daily min should not increase within one day."""

        first_now = datetime(2026, 5, 26, 15, 0, tzinfo=timezone.utc)
        second_now = datetime(2026, 5, 26, 18, 0, tzinfo=timezone.utc)

        with patch("homeassistant.util.dt.now", return_value=first_now):
            mock_ha_interface.get_daily_temperature_extrema.return_value = (28.0, 16.0)
            first_sensor_data, _ = await automation_engine._gather_sensor_data()

        with patch("homeassistant.util.dt.now", return_value=second_now):
            mock_ha_interface.get_daily_temperature_extrema.return_value = (24.0, 19.0)
            sensor_data, message = await automation_engine._gather_sensor_data()

        assert first_sensor_data is not None
        assert sensor_data is not None
        assert sensor_data.temp_max == 28.0
        assert sensor_data.temp_min == 16.0
        assert sensor_data.temp_hot == first_sensor_data.temp_hot
        assert message == ""

    async def test_gather_sensor_data_does_not_reuse_previous_day_values(self, automation_engine, mock_ha_interface):
        """Stored extrema must expire when the local day changes."""

        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        first_now = datetime(2026, 5, 26, 15, 0, tzinfo=timezone.utc)
        second_now = datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc)

        with patch("homeassistant.util.dt.now", return_value=first_now):
            first_sensor_data, _ = await automation_engine._gather_sensor_data()

        mock_ha_interface.get_daily_temperature_extrema.side_effect = InvalidSensorReadingError("weather.test", "Forecast unavailable")

        with patch("homeassistant.util.dt.now", return_value=second_now):
            sensor_data, message = await automation_engine._gather_sensor_data()

        assert first_sensor_data is not None
        assert sensor_data is not None
        assert sensor_data.temp_max is None
        assert sensor_data.temp_min is None
        assert sensor_data.temp_hot is None
        assert "skipping weather-dependent actions" in message

    async def test_run_pre_closes_when_blocked_time_range_starts(self, mock_ha_interface, mock_logger):
        """Blocked-time start should trigger one forecast-based pre-close evaluation."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_PRE_CLOSE_ENABLED.value: True,
            const.SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL: False,
            const.SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL: False,
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(28.0, 18.0, "sunny"))
        mock_ha_interface.get_sun_samples_from_sunrise_until = MagicMock(return_value=((180.0, 45.0),))

        with patch(
            "custom_components.smart_cover_automation.automation_engine.CoverAutomation.process", new=AsyncMock(return_value=CoverState())
        ) as mock_process:
            with patch("homeassistant.util.dt.now") as mock_now:
                mock_now.return_value = datetime(2026, 5, 23, 21, 55, tzinfo=timezone.utc)
                await engine.run({"cover.test": MagicMock()})

                mock_process.reset_mock()
                mock_now.return_value = datetime(2026, 5, 23, 22, 0, tzinfo=timezone.utc)
                result = await engine.run({"cover.test": MagicMock()})

        assert "cover.test" in result.covers
        assert mock_process.await_count == 1
        pre_close_sensor_data = mock_process.await_args.args[1]
        assert pre_close_sensor_data.temp_hot is True
        assert pre_close_sensor_data.weather_sunny is True
        assert pre_close_sensor_data.ignore_weather_external_controls is True
        assert pre_close_sensor_data.pre_closing is True
        assert pre_close_sensor_data.sun_samples == ((180.0, 45.0),)
        mock_ha_interface.get_forecast_snapshot_for_date.assert_awaited_once_with(
            "weather.test",
            datetime(2026, 5, 24, 22, 0, tzinfo=timezone.utc).date(),
            log_context="next-morning pre-close forecast for 2026-05-24",
        )
        mock_logger.debug.assert_any_call("Pre-closure weather conditions met, activating...")

    async def test_run_pre_closes_on_first_run_when_starting_inside_blocked_time_range_window(self, mock_ha_interface, mock_logger):
        """Startup inside the blocked-time start window should still get one pre-close evaluation."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_PRE_CLOSE_ENABLED.value: True,
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(28.0, 18.0, "sunny"))
        mock_ha_interface.get_sun_samples_from_sunrise_until = MagicMock(return_value=((180.0, 45.0),))

        with patch(
            "custom_components.smart_cover_automation.automation_engine.CoverAutomation.process", new=AsyncMock(return_value=CoverState())
        ) as mock_process:
            with patch("homeassistant.util.dt.now", return_value=datetime(2026, 5, 23, 22, 5, tzinfo=timezone.utc)):
                result = await engine.run({"cover.test": MagicMock()})

        assert "cover.test" in result.covers
        assert mock_process.await_count == 1
        mock_logger.debug.assert_any_call("Pre-closure weather conditions met, activating...")

    async def test_run_does_not_pre_close_on_first_run_when_starting_late_inside_blocked_time_range(self, mock_ha_interface, mock_logger):
        """Startup well after blocked-time start should not run pre-close for that already-active interval."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_PRE_CLOSE_ENABLED.value: True,
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(28.0, 18.0, "sunny"))
        mock_ha_interface.get_sun_samples_from_sunrise_until = MagicMock(return_value=((180.0, 45.0),))

        with patch(
            "custom_components.smart_cover_automation.automation_engine.CoverAutomation.process", new=AsyncMock(return_value=CoverState())
        ) as mock_process:
            with patch("homeassistant.util.dt.now", return_value=datetime(2026, 5, 23, 22, 15, tzinfo=timezone.utc)):
                result = await engine.run({"cover.test": MagicMock()})

        assert result.covers == {}
        assert mock_process.await_count == 0

    async def test_run_does_not_repeat_pre_close_inside_same_blocked_period(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should only run once per blocked interval."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_PRE_CLOSE_ENABLED.value: True,
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(28.0, 18.0, "sunny"))
        mock_ha_interface.get_sun_samples_from_sunrise_until = MagicMock(return_value=((180.0, 45.0),))

        with patch(
            "custom_components.smart_cover_automation.automation_engine.CoverAutomation.process", new=AsyncMock(return_value=CoverState())
        ) as mock_process:
            with patch("homeassistant.util.dt.now") as mock_now:
                mock_now.return_value = datetime(2026, 5, 23, 21, 59, tzinfo=timezone.utc)
                await engine.run({"cover.test": MagicMock()})

                mock_process.reset_mock()
                mock_now.return_value = datetime(2026, 5, 23, 22, 0, tzinfo=timezone.utc)
                await engine.run({"cover.test": MagicMock()})

                mock_process.reset_mock()
                mock_now.return_value = datetime(2026, 5, 23, 22, 1, tzinfo=timezone.utc)
                result = await engine.run({"cover.test": MagicMock()})

        assert result.covers == {}
        assert mock_process.await_count == 0

    async def test_run_skips_pre_close_when_next_morning_is_not_hot_or_sunny(self, mock_ha_interface, mock_logger):
        """Blocked-time start should skip cover processing when the forecast does not require heat protection."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_PRE_CLOSE_ENABLED.value: True,
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(15.0, 10.0, "cloudy"))
        mock_ha_interface.get_sun_samples_from_sunrise_until = MagicMock(return_value=((180.0, 45.0),))

        with patch(
            "custom_components.smart_cover_automation.automation_engine.CoverAutomation.process", new=AsyncMock(return_value=CoverState())
        ) as mock_process:
            with patch("homeassistant.util.dt.now") as mock_now:
                mock_now.return_value = datetime(2026, 5, 23, 21, 59, tzinfo=timezone.utc)
                await engine.run({"cover.test": MagicMock()})

                mock_process.reset_mock()
                mock_now.return_value = datetime(2026, 5, 23, 22, 0, tzinfo=timezone.utc)
                result = await engine.run({"cover.test": MagicMock()})

        assert result.covers == {}
        assert mock_process.await_count == 0
        mock_logger.debug.assert_any_call("Pre-closure weather conditions not met, skipping...")
        mock_logger.info.assert_any_call(
            "Blocked time range started; skipping pre-close because the next morning is not forecast to be both hot and sunny"
        )

    async def test_build_blocked_time_range_pre_close_sensor_data_returns_sensor_snapshot(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close sensor snapshot should use the forecast for the blocked-range end date."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(9, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(17, 0),
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_sun_samples_from_sunrise_until.return_value = ((150.0, 12.0), (200.0, 30.0))
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(24.0, 16.0, "partlycloudy"))

        with patch("homeassistant.util.dt.now", return_value=datetime(2026, 5, 23, 9, 0, tzinfo=timezone.utc)):
            sensor_data, message = await engine._build_blocked_time_range_pre_close_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is True
        assert sensor_data.weather_sunny is True
        assert sensor_data.ignore_weather_external_controls is True
        assert sensor_data.pre_closing is True
        assert sensor_data.sun_samples == ((150.0, 12.0), (200.0, 30.0))
        assert message == ""
        mock_logger.debug.assert_any_call(
            "Next day weather temperature state for pre-closure: %s (daily_max=%s, daily_min=%s, max_threshold_met=%s, min_threshold_met=%s)",
            "hot",
            24.0,
            16.0,
            True,
            True,
        )
        mock_logger.debug.assert_any_call("Next day weather condition used for pre-closure: %s", "sunny")
        mock_ha_interface.get_forecast_snapshot_for_date.assert_awaited_once_with(
            "weather.test",
            datetime(2026, 5, 23, 17, 0, tzinfo=timezone.utc).date(),
            log_context="next-morning pre-close forecast for 2026-05-23",
        )

    async def test_build_blocked_time_range_pre_close_sensor_data_handles_future_sun_error(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should stop when future sun data cannot be resolved."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_sun_samples_from_sunrise_until.side_effect = RuntimeError("boom")

        sensor_data, message = await engine._build_blocked_time_range_pre_close_sensor_data()

        assert sensor_data is None
        assert "future sun data is unavailable" in message

    async def test_build_blocked_time_range_pre_close_sensor_data_collects_weather_errors(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should collect forecast errors and still return the partial snapshot."""

        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_sun_samples_from_sunrise_until.return_value = ((180.0, 45.0),)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(
            side_effect=InvalidSensorReadingError("weather.test", "forecast missing")
        )

        sensor_data, message = await engine._build_blocked_time_range_pre_close_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is None
        assert sensor_data.weather_sunny is None
        assert "Forecast temperature unavailable" in message
        assert "Forecast sunshine state unavailable" in message

    async def test_build_blocked_time_range_pre_close_sensor_data_uses_partial_forecast_snapshot(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should keep partial snapshot values when one forecast field is missing."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_sun_samples_from_sunrise_until.return_value = ((180.0, 45.0),)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(24.0, 16.0, None))

        sensor_data, message = await engine._build_blocked_time_range_pre_close_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is True
        assert sensor_data.weather_sunny is None
        assert "Forecast sunshine state unavailable" in message
        mock_logger.debug.assert_any_call(
            "Next day weather temperature state for pre-closure: %s (daily_max=%s, daily_min=%s, max_threshold_met=%s, min_threshold_met=%s)",
            "hot",
            24.0,
            16.0,
            True,
            True,
        )
        mock_logger.debug.assert_any_call("Next day weather condition used for pre-closure: %s", "unknown")

    async def test_build_blocked_time_range_pre_close_sensor_data_handles_missing_max_temperature(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should report a missing forecast temperature when the snapshot has no max."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_sun_samples_from_sunrise_until.return_value = ((180.0, 45.0),)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(return_value=(None, 16.0, "sunny"))

        sensor_data, message = await engine._build_blocked_time_range_pre_close_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is None
        assert sensor_data.weather_sunny is True
        assert "Forecast temperature unavailable" in message

    async def test_build_blocked_time_range_pre_close_sensor_data_handles_unexpected_forecast_error(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should degrade gracefully when explicit-date forecast lookup fails unexpectedly."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)
        mock_ha_interface.get_sun_samples_from_sunrise_until.return_value = ((180.0, 45.0),)
        mock_ha_interface.get_forecast_snapshot_for_date = AsyncMock(side_effect=RuntimeError("boom"))

        sensor_data, message = await engine._build_blocked_time_range_pre_close_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is None
        assert sensor_data.weather_sunny is None
        assert "Forecast temperature unavailable" in message
        assert "Forecast sunshine state unavailable" in message
        mock_logger.error.assert_any_call("Unexpected error getting forecast snapshot for blocked-time pre-close: boom")

    def test_get_blocked_time_range_start_datetime_rolls_back_for_overnight_period_before_end(self, mock_ha_interface, mock_logger):
        """Overnight blocked-range start should resolve to the previous day before the end time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(22, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(6, 0),
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        result = engine._get_blocked_time_range_start_datetime(datetime(2026, 5, 24, 5, 0, tzinfo=timezone.utc))

        assert result == datetime(2026, 5, 23, 22, 0, tzinfo=timezone.utc)

    async def test_run_blocked_time_range_pre_close_skips_when_forecast_does_not_match(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should skip cover processing when the next morning is not both hot and sunny."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        sensor_data = SensorData(180.0, 45.0, 18.0, 12.0, False, "cloudy", False, False, False, ignore_weather_external_controls=True)

        with patch.object(engine, "_build_blocked_time_range_pre_close_sensor_data", AsyncMock(return_value=(sensor_data, ""))):
            with patch.object(engine, "_process_covers", AsyncMock()) as mock_process_covers:
                message = await engine._run_blocked_time_range_pre_close({"cover.test": MagicMock()}, MagicMock())

        mock_process_covers.assert_not_awaited()
        assert message == "Blocked time range started; skipping pre-close because the next morning is not forecast to be both hot and sunny"

    def test_time_period_disabled_outside_same_day_range(self, mock_ha_interface, mock_logger):
        """Same-day disabled periods should remain inactive before the configured start time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: time(9, 0),
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: time(17, 0),
        }
        engine = AutomationEngine(
            resolved=resolve(config),
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        with patch("homeassistant.util.dt.now") as mock_now:
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(8, 59)
            mock_now.return_value = mock_datetime

            is_disabled, period_string = engine._in_time_period_automation_disabled()

        assert is_disabled is False
        assert period_string == ""

    @pytest.mark.parametrize(
        ("start_time", "end_time", "reference_time", "expected_date"),
        [
            (time(9, 0), time(17, 0), datetime(2026, 5, 23, 9, 0, tzinfo=timezone.utc), datetime(2026, 5, 23, 17, 0, tzinfo=timezone.utc)),
            (time(22, 0), time(6, 0), datetime(2026, 5, 23, 22, 0, tzinfo=timezone.utc), datetime(2026, 5, 24, 6, 0, tzinfo=timezone.utc)),
        ],
    )
    def test_get_blocked_time_range_end_datetime(
        self,
        mock_ha_interface,
        mock_logger,
        start_time: time,
        end_time: time,
        reference_time: datetime,
        expected_date: datetime,
    ) -> None:
        """Blocked-time end datetime should stay on the same day or roll over overnight as configured."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value: start_time,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value: end_time,
        }
        engine = AutomationEngine(resolved=resolve(config), config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        result = engine._get_blocked_time_range_end_datetime(reference_time)

        assert result == expected_date

    async def test_run_blocked_time_range_pre_close_processes_covers_when_forecast_matches(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should process covers when the forecast snapshot requires heat protection."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        sensor_data = SensorData(180.0, 45.0, 25.0, 18.0, True, "sunny", True, False, False, ignore_weather_external_controls=True)
        result = MagicMock()

        with patch.object(engine, "_build_blocked_time_range_pre_close_sensor_data", AsyncMock(return_value=(sensor_data, ""))):
            with patch.object(engine, "_process_covers", AsyncMock()) as mock_process_covers:
                message = await engine._run_blocked_time_range_pre_close({"cover.test": MagicMock()}, result)

        mock_process_covers.assert_awaited_once()
        assert "ran forecast-based pre-close evaluation" in message

    async def test_run_blocked_time_range_pre_close_returns_error_message_when_snapshot_missing(self, mock_ha_interface, mock_logger):
        """Blocked-time pre-close should return the sensor-build error message unchanged."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        with patch.object(
            engine,
            "_build_blocked_time_range_pre_close_sensor_data",
            AsyncMock(return_value=(None, "pre-close failed")),
        ):
            message = await engine._run_blocked_time_range_pre_close({"cover.test": MagicMock()}, MagicMock())

        assert message == "pre-close failed"

    @pytest.mark.parametrize(
        "failing_call,expected_message",
        [
            (
                "forecast",
                "Weather forecast unavailable due to an unexpected error, continuing with last known forecast temperatures",
            ),
            (
                "condition",
                "Weather condition unavailable due to an unexpected error, continuing with last known weather condition",
            ),
        ],
    )
    async def test_gather_sensor_data_unexpected_weather_error_uses_cached_values(
        self,
        automation_engine,
        mock_ha_interface,
        failing_call: str,
        expected_message: str,
    ):
        """Unexpected weather errors should reuse cached weather values when available."""

        first_sensor_data, first_message = await automation_engine._gather_sensor_data()

        assert first_sensor_data is not None
        assert first_message == ""

        if failing_call == "forecast":
            mock_ha_interface.get_daily_temperature_extrema.side_effect = RuntimeError("Unexpected weather error")
        else:
            mock_ha_interface.get_weather_condition.side_effect = RuntimeError("Unexpected weather condition error")

        sensor_data, message = await automation_engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_max == first_sensor_data.temp_max
        assert sensor_data.temp_min == first_sensor_data.temp_min
        assert sensor_data.temp_hot == first_sensor_data.temp_hot
        assert sensor_data.weather_condition == first_sensor_data.weather_condition
        assert sensor_data.weather_sunny == first_sensor_data.weather_sunny
        assert expected_message in message

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
        mock_ha_interface.get_daily_temperature_extrema.side_effect = RuntimeError("Unexpected weather error")

        # Call method
        sensor_data, message = await automation_engine._gather_sensor_data()

        # Verify error handling
        assert sensor_data is not None
        assert sensor_data.temp_max is None
        assert sensor_data.temp_hot is None
        assert "unexpected error" in message.lower()


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

    def test_check_global_conditions_time_period_disabled(self, mock_ha_interface, mock_logger):
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
            logger=mock_logger,
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


class TestTimeCalculationHelpers:
    """Test helper methods that compute daily schedule datetimes."""

    def test_get_local_datetime_for_date_uses_target_date_and_time(self, automation_engine, freezer):
        """Test local datetime construction for one date/time pair."""
        freezer.move_to("2025-11-05 08:00:00")

        result = automation_engine._get_local_datetime_for_date(dt_util.now().date(), time(21, 15))

        assert result.year == 2025
        assert result.month == 11
        assert result.day == 5
        assert result.hour == 21
        assert result.minute == 15
        assert result.tzinfo is not None

    def test_get_evening_closure_time_for_date_fixed_time(self, mock_ha_interface, mock_logger, freezer):
        """Test evening closure datetime calculation in fixed-time mode."""
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:15:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-05 08:00:00")
        result = engine._get_evening_closure_time_for_date(dt_util.now().date())

        assert result is not None
        assert result.hour == 21
        assert result.minute == 15

    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_get_evening_closure_time_for_date_after_sunset_applies_delay(self, mock_get_astral, mock_ha_interface, mock_logger):
        """Test evening closure datetime calculation in after-sunset mode."""
        from datetime import datetime

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        mock_get_astral.return_value = datetime(2025, 11, 5, 18, 30, 0, tzinfo=dt_util.get_default_time_zone())

        result = engine._get_evening_closure_time_for_date(date(2025, 11, 5))

        assert result == datetime(2025, 11, 5, 18, 45, 0, tzinfo=dt_util.get_default_time_zone())

    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_get_evening_closure_time_for_date_returns_none_when_sunset_unavailable(self, mock_get_astral, mock_ha_interface, mock_logger):
        """Test evening closure datetime calculation when sunset data is unavailable."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        mock_get_astral.return_value = None

        assert engine._get_evening_closure_time_for_date(date(2025, 11, 5)) is None

    def test_get_evening_closure_time_for_date_external_valid(self, mock_ha_interface, mock_logger, freezer):
        """Test evening closure datetime calculation in external mode with a valid entity time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_MODE.value: "external",
            const.TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME: "18:20:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-05 06:00:00")
        result = engine._get_evening_closure_time_for_date(date(2025, 11, 5))

        assert result is not None
        assert result.hour == 18
        assert result.minute == 20

    def test_get_evening_closure_time_for_date_external_missing_returns_none(self, mock_ha_interface, mock_logger):
        """Test evening closure datetime calculation in external mode without an entity time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_MODE.value: "external",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        assert engine._get_evening_closure_time_for_date(date(2025, 11, 5)) is None

    def test_get_evening_closure_time_for_date_external_invalid_returns_none(self, mock_ha_interface, mock_logger):
        """Test evening closure datetime calculation in external mode with an invalid entity time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_MODE.value: "external",
            const.TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME: "not-a-time",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        assert engine._get_evening_closure_time_for_date(date(2025, 11, 5)) is None

    def test_get_morning_opening_time_for_date_external_valid(self, mock_ha_interface, mock_logger, freezer):
        """Test morning opening datetime calculation in external mode with a valid entity time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.MORNING_OPENING_MODE.value: "external",
            const.TIME_KEY_MORNING_OPENING_EXTERNAL_TIME: "08:20:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-05 06:00:00")
        result = engine._get_morning_opening_time_for_date(date(2025, 11, 5))

        assert result is not None
        assert result.hour == 8
        assert result.minute == 20

    def test_get_morning_opening_time_for_date_external_missing_returns_none(self, mock_ha_interface, mock_logger):
        """Test morning opening datetime calculation in external mode without an entity time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.MORNING_OPENING_MODE.value: "external",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        assert engine._get_morning_opening_time_for_date(date(2025, 11, 5)) is None

    def test_get_morning_opening_time_for_date_external_invalid_returns_none(self, mock_ha_interface, mock_logger):
        """Test morning opening datetime calculation in external mode with an invalid entity time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.MORNING_OPENING_MODE.value: "external",
            const.TIME_KEY_MORNING_OPENING_EXTERNAL_TIME: "not-a-time",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        assert engine._get_morning_opening_time_for_date(date(2025, 11, 5)) is None

    def test_in_time_period_automation_disabled_uses_external_bounds(self, mock_ha_interface, mock_logger, freezer):
        """Blocked-time checks should honor external start and end times when configured."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_MODE.value: const.BlockedTimeRangeMode.EXTERNAL,
            const.TIME_KEY_AUTOMATION_DISABLED_TIME_RANGE_EXTERNAL_START: "22:00:00",
            const.TIME_KEY_AUTOMATION_DISABLED_TIME_RANGE_EXTERNAL_END: "06:00:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-05 23:15:00")
        assert engine._in_time_period_automation_disabled() == (True, "22:00:00 - 06:00:00")

    def test_in_time_period_automation_disabled_returns_inactive_when_external_bounds_invalid(self, mock_ha_interface, mock_logger):
        """Invalid external blocked-time boundaries should disable blocked-time evaluation safely."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value: True,
            ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_MODE.value: const.BlockedTimeRangeMode.EXTERNAL,
            const.TIME_KEY_AUTOMATION_DISABLED_TIME_RANGE_EXTERNAL_START: "not-a-time",
            const.TIME_KEY_AUTOMATION_DISABLED_TIME_RANGE_EXTERNAL_END: "06:00:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        assert engine._in_time_period_automation_disabled() == (False, "")

    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_get_morning_opening_time_for_date_relative_returns_none_when_sunrise_unavailable(
        self, mock_get_astral, mock_ha_interface, mock_logger
    ):
        """Test relative morning opening when sunrise data is unavailable."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.MORNING_OPENING_MODE.value: "relative_to_sunrise",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        mock_get_astral.return_value = None

        assert engine._get_morning_opening_time_for_date(date(2025, 11, 5)) is None


class TestInTimePeriodAutomationDisabled:
    """Test _in_time_period_automation_disabled method."""

    def test_time_period_disabled_not_configured(self, automation_engine):
        """Test when time period disabling is not configured."""
        # Call method
        is_disabled, period_string = automation_engine._in_time_period_automation_disabled()

        # Verify results
        assert is_disabled is False
        assert period_string == ""

    def test_time_period_disabled_outside_range(self, mock_ha_interface, mock_logger):
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
            logger=mock_logger,
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

    def test_time_period_disabled_inside_overnight_range(self, mock_ha_interface, mock_logger):
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
            logger=mock_logger,
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

    def test_time_period_disabled_inside_same_day_range(self, mock_ha_interface, mock_logger):
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
            logger=mock_logger,
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

    async def test_run_with_disabled_automation(self, mock_ha_interface, mock_logger):
        """Disabled automation should return early before gathering sensor data."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.ENABLED.value: False,
        }
        engine = AutomationEngine(
            resolved=resolve(config),
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        with patch.object(engine, "cancel_pending_cover_executions") as mock_cancel:
            with patch.object(engine, "_gather_sensor_data", AsyncMock()) as mock_gather:
                result = await engine.run({"cover.test": MagicMock()})

        assert result.covers == {}
        mock_cancel.assert_called_once()
        mock_gather.assert_not_awaited()

    async def test_run_with_all_covers_unavailable_skips_sensor_lookup(self, mock_ha_interface, mock_logger):
        """All-unavailable cover states should return early without sensor lookups."""

        config = {
            ConfKeys.COVERS.value: ["cover.test_1", "cover.test_2"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        }
        engine = AutomationEngine(
            resolved=resolve(config),
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        with patch.object(engine, "cancel_pending_cover_executions") as mock_cancel:
            with patch.object(engine, "_gather_sensor_data", AsyncMock()) as mock_gather:
                result = await engine.run({"cover.test_1": None, "cover.test_2": None})

        assert result.covers == {}
        mock_cancel.assert_called_once()
        mock_gather.assert_not_awaited()

    async def test_run_with_no_covers_configured(self, mock_ha_interface, mock_logger):
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
            logger=mock_logger,
        )

        # Call run
        result = await engine.run({})

        # Verify result
        assert result.covers == {}

    async def test_run_with_automation_disabled(self, mock_ha_interface, mock_logger):
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
            logger=mock_logger,
        )

        # Call run
        cover_states = {"cover.test": MagicMock()}
        result = await engine.run(cover_states)  # type: ignore[arg-type]

        # Verify result
        assert result.covers == {}

    async def test_run_with_all_covers_unavailable(self, automation_engine):
        """Test run when all covers are unavailable."""
        # Call run with all covers unavailable
        cover_states = {"cover.test": None}
        result = await automation_engine.run(cover_states)

        # Verify result
        assert result.covers == {}

    async def test_run_with_sensor_data_unavailable(self, automation_engine, mock_ha_interface):
        """Test run when sensor data is unavailable."""
        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        # Configure mock to return error
        mock_ha_interface.get_sun_data.side_effect = InvalidSensorReadingError("sun.sun", "unavailable")

        # Call run
        cover_states = {"cover.test": MagicMock()}
        result = await automation_engine.run(cover_states)  # type: ignore[arg-type]

        # Verify result
        assert result.covers == {}

    async def test_run_stores_sensor_data_in_result(self, automation_engine, mock_ha_interface):
        """Test that sensor data is stored in the result."""
        # Configure mocks
        mock_ha_interface.get_sun_data.return_value = (180.0, 45.0)
        mock_ha_interface.get_daily_temperature_extrema.return_value = (25.0, 18.0)
        mock_ha_interface.get_weather_condition.return_value = "sunny"

        # Call run
        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {}
        cover_states = {"cover.test": cover_state}
        result = await automation_engine.run(cover_states)  # type: ignore[arg-type]

        # Verify sensor data in result
        assert result.sun_azimuth == 180.0
        assert result.sun_elevation == 45.0
        assert result.temp_current_max == 25.0
        assert result.temp_hot is not None
        assert result.weather_sunny is not None

    async def test_run_blocked_by_nighttime(self, mock_ha_interface, mock_logger):
        """Test run when blocked by opening block after evening closure."""
        # Configure to block after evening closure
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            f"cover.test_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        # Configure mocks - sun is below horizon
        mock_ha_interface.get_sun_state.return_value = const.HA_SUN_STATE_BELOW_HORIZON

        # Call run
        cover_state = MagicMock()
        cover_states = {"cover.test": cover_state}
        result = await engine.run(cover_states)  # type: ignore[arg-type]

        # Verify automation was blocked - cover should be in result but with no target position
        assert "cover.test" in result.covers
        assert result.covers["cover.test"].pos_target_desired is None

    async def test_run_logs_debug_on_first_unavailable_sensor_iteration(self, automation_engine, mock_ha_interface):
        """Test first unavailable sensor iteration is logged at debug severity."""
        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        mock_ha_interface.get_sun_data.side_effect = InvalidSensorReadingError("sun.sun", "unavailable")

        await automation_engine.run({"cover.test": MagicMock()})  # type: ignore[arg-type]

        automation_engine._logger.debug.assert_called()
        automation_engine._logger.warning.assert_not_called()

    async def test_run_logs_warning_on_second_unavailable_sensor_iteration(self, automation_engine, mock_ha_interface):
        """Test repeated unavailable sensor iterations are logged at warning severity."""
        from custom_components.smart_cover_automation.ha_interface import InvalidSensorReadingError

        mock_ha_interface.get_sun_data.side_effect = InvalidSensorReadingError("sun.sun", "unavailable")

        await automation_engine.run({"cover.test": MagicMock()})  # type: ignore[arg-type]
        await automation_engine.run({"cover.test": MagicMock()})  # type: ignore[arg-type]

        automation_engine._logger.warning.assert_called()

    async def test_run_logs_lock_state_when_active(self, mock_ha_interface, mock_logger):
        """Test that an active lock mode is logged during run()."""
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.LOCK_MODE.value: "hold_position",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {}

        await engine.run({"cover.test": cover_state})  # type: ignore[arg-type]

        mock_logger.warning.assert_any_call(f"Cover lock active: {const.LockMode.HOLD_POSITION}")

    @patch("custom_components.smart_cover_automation.automation_engine.CoverAutomation.process", new_callable=AsyncMock)
    async def test_run_global_block_stops_cover_processing(self, mock_process, automation_engine):
        """Test that global blocking returns early before any cover is processed."""
        with patch.object(
            automation_engine,
            "_check_global_conditions",
            return_value=(False, "blocked", const.LogSeverity.DEBUG),
        ):
            result = await automation_engine.run({"cover.test": MagicMock()})  # type: ignore[arg-type]

        assert result.covers == {}
        mock_process.assert_not_called()

    @patch("custom_components.smart_cover_automation.automation_engine.CoverAutomation.process", new_callable=AsyncMock)
    async def test_run_processes_multiple_covers(self, mock_process, mock_ha_interface, mock_logger):
        """Test that run() processes every configured cover state."""
        config = {
            ConfKeys.COVERS.value: ["cover.test_1", "cover.test_2"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        mock_process.side_effect = [MagicMock(name="cover_1_result"), MagicMock(name="cover_2_result")]

        result = await engine.run(
            {"cover.test_1": MagicMock(), "cover.test_2": None}  # type: ignore[arg-type]
        )

        assert set(result.covers) == {"cover.test_1", "cover.test_2"}
        assert mock_process.await_count == 2

    @patch("custom_components.smart_cover_automation.automation_engine.CoverAutomation.execute_plan", new_callable=AsyncMock)
    @patch("custom_components.smart_cover_automation.automation_engine.CoverAutomation.evaluate", new_callable=AsyncMock)
    async def test_run_queues_later_cover_actions_when_stagger_enabled(
        self,
        mock_evaluate,
        mock_execute_plan,
        mock_ha_interface,
        mock_logger,
    ):
        """Test that only the first actionable cover executes immediately when staggering is enabled."""

        config = {
            ConfKeys.COVERS.value: ["cover.test_1", "cover.test_2"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.COVER_MOVEMENT_STAGGER_DELAY.value: 15,
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        sensor_data = SensorData(180.0, 45.0, 25.0, 18.0, True, "sunny", True, False, False)
        plan_1 = CoverExecutionPlan(
            cover_state=CoverState(pos_current=10, pos_target_desired=20),
            sensor_data=sensor_data,
            features=0,
            current_pos=10,
            desired_pos=20,
            movement_reason=CoverMovementReason.OPENING_LET_LIGHT_IN,
            planned_tilt_target=None,
        )
        plan_2 = CoverExecutionPlan(
            cover_state=CoverState(pos_current=30, pos_target_desired=40),
            sensor_data=sensor_data,
            features=0,
            current_pos=30,
            desired_pos=40,
            movement_reason=CoverMovementReason.OPENING_LET_LIGHT_IN,
            planned_tilt_target=None,
        )
        mock_evaluate.side_effect = [
            (plan_1.cover_state, plan_1),
            (plan_2.cover_state, plan_2),
        ]

        with patch.object(engine, "_schedule_pending_cover_execution") as mock_schedule:
            result = await engine.run(
                {
                    "cover.test_1": MagicMock(),
                    "cover.test_2": MagicMock(),
                }
            )

        mock_execute_plan.assert_awaited_once_with(plan_1)
        mock_schedule.assert_called_once()
        assert result.covers["cover.test_1"] == mock_execute_plan.return_value
        assert result.covers["cover.test_2"] == plan_2.cover_state

    @patch("custom_components.smart_cover_automation.automation_engine.CoverAutomation.evaluate", new_callable=AsyncMock)
    async def test_run_cancels_pending_execution_when_evaluate_returns_no_plan(
        self,
        mock_evaluate,
        mock_ha_interface,
        mock_logger,
    ):
        """Staggered processing should cancel stale queued work when no action remains."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.COVER_MOVEMENT_STAGGER_DELAY.value: 15,
        }
        engine = AutomationEngine(
            resolved=resolve(config),
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        cover_state = CoverState(pos_current=10, pos_target_desired=10)
        mock_evaluate.return_value = (cover_state, None)

        with patch.object(engine, "_cancel_pending_cover_execution") as mock_cancel:
            result = await engine.run({"cover.test": MagicMock()})

        assert result.covers["cover.test"] == cover_state
        mock_cancel.assert_called_once_with("cover.test", "no queued action remains valid")


class TestPendingCoverExecutionQueue:
    """Test delayed cover execution queue helpers."""

    @staticmethod
    def _make_plan(desired_pos: int = 20) -> CoverExecutionPlan:
        """Create a minimal execution plan for queue tests."""

        sensor_data = SensorData(180.0, 45.0, 25.0, 18.0, True, "sunny", True, False, False)
        return CoverExecutionPlan(
            cover_state=CoverState(pos_current=10, pos_target_desired=desired_pos),
            sensor_data=sensor_data,
            features=0,
            current_pos=10,
            desired_pos=desired_pos,
            movement_reason=CoverMovementReason.OPENING_LET_LIGHT_IN,
            planned_tilt_target=None,
        )

    def test_schedule_pending_cover_execution_ignores_equivalent_later_plan(self, mock_ha_interface, mock_logger):
        """Equivalent queued executions should not be rescheduled when the existing one runs sooner."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        plan = self._make_plan()
        existing = ScheduledCoverExecution(
            schedule_id=1,
            execute_at=datetime(2026, 5, 23, 10, 5, tzinfo=timezone.utc),
            generation=0,
            plan_signature=plan.signature,
            task=MagicMock(),
        )
        engine._pending_cover_executions["cover.test"] = existing

        with patch("custom_components.smart_cover_automation.automation_engine.asyncio.create_task") as mock_create_task:
            engine._schedule_pending_cover_execution(
                "cover.test",
                MagicMock(),
                plan,
                datetime(2026, 5, 23, 10, 10, tzinfo=timezone.utc),
                generation=0,
            )

        assert engine._pending_cover_executions["cover.test"] is existing
        mock_create_task.assert_not_called()

    def test_schedule_pending_cover_execution_adds_new_plan(self, mock_ha_interface, mock_logger):
        """A new queued execution should be stored and logged when no pending entry exists yet."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        plan = self._make_plan()
        created_task = MagicMock(spec=asyncio.Task)

        def create_task_side_effect(coroutine):
            coroutine.close()
            return created_task

        with patch(
            "custom_components.smart_cover_automation.automation_engine.dt_util.utcnow",
            return_value=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
        ):
            with patch(
                "custom_components.smart_cover_automation.automation_engine.asyncio.create_task",
                side_effect=create_task_side_effect,
            ):
                engine._schedule_pending_cover_execution(
                    "cover.test",
                    MagicMock(),
                    plan,
                    datetime(2026, 5, 23, 10, 1, tzinfo=timezone.utc),
                    generation=2,
                )

        scheduled = engine._pending_cover_executions["cover.test"]
        assert scheduled.schedule_id == 1
        assert scheduled.generation == 2
        assert scheduled.plan_signature == plan.signature
        assert scheduled.task is created_task
        mock_logger.info.assert_any_call("[%s] Queued cover execution in %.0f s", "cover.test", 60.0)

    def test_schedule_pending_cover_execution_replaces_superseded_plan(self, mock_ha_interface, mock_logger):
        """A newer queued execution should replace the existing pending one when the plan changes."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        existing_plan = self._make_plan(20)
        new_plan = self._make_plan(30)
        engine._pending_cover_executions["cover.test"] = ScheduledCoverExecution(
            schedule_id=1,
            execute_at=datetime(2026, 5, 23, 10, 5, tzinfo=timezone.utc),
            generation=0,
            plan_signature=existing_plan.signature,
            task=MagicMock(),
        )
        created_task = MagicMock(spec=asyncio.Task)

        def create_task_side_effect(coroutine):
            coroutine.close()
            return created_task

        with patch.object(engine, "_cancel_pending_cover_execution") as mock_cancel:
            with patch(
                "custom_components.smart_cover_automation.automation_engine.dt_util.utcnow",
                return_value=datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc),
            ):
                with patch(
                    "custom_components.smart_cover_automation.automation_engine.asyncio.create_task",
                    side_effect=create_task_side_effect,
                ):
                    engine._schedule_pending_cover_execution(
                        "cover.test",
                        MagicMock(),
                        new_plan,
                        datetime(2026, 5, 23, 10, 10, tzinfo=timezone.utc),
                        generation=1,
                    )

        mock_cancel.assert_called_once_with("cover.test", "superseded by a newer cover plan")
        scheduled = engine._pending_cover_executions["cover.test"]
        assert scheduled.plan_signature == new_plan.signature
        assert scheduled.generation == 1
        assert scheduled.task is created_task
        mock_logger.info.assert_any_call("[%s] Queued cover execution in %.0f s", "cover.test", 600.0)

    async def test_run_pending_cover_execution_logs_execute_errors(self, mock_ha_interface, mock_logger):
        """Queued execution should log plan execution failures and clear the pending entry."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        plan = self._make_plan()
        cover_automation = MagicMock()
        cover_automation.execute_plan = AsyncMock(side_effect=RuntimeError("boom"))
        engine._pending_cover_executions["cover.test"] = ScheduledCoverExecution(
            schedule_id=7,
            execute_at=datetime(2026, 5, 23, 10, 5, tzinfo=timezone.utc),
            generation=0,
            plan_signature=plan.signature,
            task=MagicMock(),
        )

        with patch("custom_components.smart_cover_automation.automation_engine.asyncio.sleep", new=AsyncMock()):
            await engine._run_pending_cover_execution("cover.test", 7, cover_automation, plan, delay_seconds=0)

        assert "cover.test" not in engine._pending_cover_executions
        mock_logger.error.assert_called_once()
        assert mock_logger.error.call_args.args[:2] == ("[%s] Failed queued cover execution: %s", "cover.test")
        assert isinstance(mock_logger.error.call_args.args[2], RuntimeError)
        assert str(mock_logger.error.call_args.args[2]) == "boom"

    async def test_run_pending_cover_execution_returns_when_sleep_is_cancelled(self, mock_ha_interface, mock_logger):
        """Queued execution should stop quietly when the scheduled delay is cancelled."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        plan = self._make_plan()
        cover_automation = MagicMock()
        cover_automation.execute_plan = AsyncMock()
        engine._pending_cover_executions["cover.test"] = ScheduledCoverExecution(
            schedule_id=7,
            execute_at=datetime(2026, 5, 23, 10, 5, tzinfo=timezone.utc),
            generation=0,
            plan_signature=plan.signature,
            task=MagicMock(),
        )

        async def raise_cancelled(_delay_seconds: float) -> None:
            raise asyncio.CancelledError

        with patch("custom_components.smart_cover_automation.automation_engine.asyncio.sleep", side_effect=raise_cancelled):
            await engine._run_pending_cover_execution("cover.test", 7, cover_automation, plan, delay_seconds=0)

        assert "cover.test" in engine._pending_cover_executions
        cover_automation.execute_plan.assert_not_awaited()

    async def test_run_pending_cover_execution_returns_when_schedule_is_missing(self, mock_ha_interface, mock_logger):
        """Queued execution should stop quietly when the pending entry was already removed."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        cover_automation = MagicMock()
        cover_automation.execute_plan = AsyncMock()

        with patch("custom_components.smart_cover_automation.automation_engine.asyncio.sleep", new=AsyncMock()):
            await engine._run_pending_cover_execution("cover.test", 7, cover_automation, self._make_plan(), delay_seconds=0)

        cover_automation.execute_plan.assert_not_awaited()

    async def test_run_pending_cover_execution_returns_when_schedule_id_changes(self, mock_ha_interface, mock_logger):
        """Queued execution should stop when a newer pending schedule replaced the original one."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.test"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        plan = self._make_plan()
        cover_automation = MagicMock()
        cover_automation.execute_plan = AsyncMock()
        engine._pending_cover_executions["cover.test"] = ScheduledCoverExecution(
            schedule_id=8,
            execute_at=datetime(2026, 5, 23, 10, 5, tzinfo=timezone.utc),
            generation=0,
            plan_signature=plan.signature,
            task=MagicMock(),
        )

        with patch("custom_components.smart_cover_automation.automation_engine.asyncio.sleep", new=AsyncMock()):
            await engine._run_pending_cover_execution("cover.test", 7, cover_automation, plan, delay_seconds=0)

        assert "cover.test" in engine._pending_cover_executions
        cover_automation.execute_plan.assert_not_awaited()

    def test_cancel_pending_cover_executions_for_removed_covers(self, mock_ha_interface, mock_logger):
        """Queued executions should be cancelled when their covers are no longer configured."""

        engine = AutomationEngine(
            resolved=resolve({ConfKeys.COVERS.value: ["cover.keep", "cover.remove"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"}),
            config={ConfKeys.COVERS.value: ["cover.keep", "cover.remove"], ConfKeys.WEATHER_ENTITY_ID.value: "weather.test"},
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        plan = self._make_plan()
        engine._pending_cover_executions["cover.keep"] = ScheduledCoverExecution(
            schedule_id=1,
            execute_at=datetime(2026, 5, 23, 10, 5, tzinfo=timezone.utc),
            generation=0,
            plan_signature=plan.signature,
            task=MagicMock(),
        )
        engine._pending_cover_executions["cover.remove"] = ScheduledCoverExecution(
            schedule_id=2,
            execute_at=datetime(2026, 5, 23, 10, 6, tzinfo=timezone.utc),
            generation=0,
            plan_signature=plan.signature,
            task=MagicMock(),
        )

        with patch.object(engine, "_cancel_pending_cover_execution") as mock_cancel:
            engine._cancel_pending_cover_executions_for_removed_covers(("cover.keep",))

        mock_cancel.assert_called_once_with("cover.remove", "cover no longer configured")


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
    """Test _check_evening_closure method for evening closure feature.

    The evening closure uses a window-based approach for reliability:
    - Window starts at: sunset + configured delay
    - Window ends at: window_start + SUNSET_CLOSING_WINDOW_MINUTES (10 min)
    - Covers close once when first entering the window
    - State resets after window ends
    """

    #
    # test_check_sunset_closing_feature_disabled
    #
    def test_check_sunset_closing_feature_disabled(self, mock_ha_interface, mock_logger):
        """Test that method returns False when feature is disabled."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: False,
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        result = engine._check_evening_closure()

        assert result is False

    #
    # test_check_sunset_closing_before_window
    #
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_check_sunset_closing_before_window(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that method returns False when current time is before the closing window."""
        from datetime import datetime

        # Setup: feature enabled with 15 minute delay
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        # Freeze time to 18:00 (before sunset + delay window)
        freezer.move_to("2025-11-04 18:00:00")

        # Mock sunset at 18:30 - window starts at 18:45 (sunset + 15 min delay)
        sunset_time = datetime(2025, 11, 4, 18, 30, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunset_time

        result = engine._check_evening_closure()

        assert result is False
        assert engine._evening_covers_closed is False

    #
    # test_check_sunset_closing_inside_window_first_time
    #
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_check_sunset_closing_inside_window_first_time(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that method returns True once when entering the closing window."""
        from datetime import datetime

        # Setup: feature enabled with 15 minute delay
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        # Freeze time to 18:47 (inside window: 18:45 to 18:55)
        freezer.move_to("2025-11-04 18:47:00")

        # Mock sunset at 18:30 - window starts at 18:45 (sunset + 15 min delay)
        sunset_time = datetime(2025, 11, 4, 18, 30, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunset_time

        # First call: should return True
        result = engine._check_evening_closure()
        assert result is True

    def test_check_evening_closure_fixed_time_window_lifecycle(self, mock_ha_interface, mock_logger, freezer):
        """Test the fixed-time evening closure window before, during, and after the active period."""
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-04 20:55:00")
        assert engine._check_evening_closure() is False

        freezer.move_to("2025-11-04 21:05:00")
        assert engine._check_evening_closure() is True

        freezer.move_to("2025-11-04 21:06:00")
        assert engine._check_evening_closure() is False
        assert engine._evening_covers_closed is True

        freezer.move_to("2025-11-04 21:15:00")
        assert engine._check_evening_closure() is False
        assert engine._evening_covers_closed is False


class TestComputePostEveningClosure:
    """Test _compute_post_evening_closure with morning opening settings."""

    @pytest.mark.parametrize(
        (
            "morning_mode",
            "morning_time",
            "external_time",
            "sunrise_time",
            "now_string",
            "expected",
        ),
        [
            (
                const.MorningOpeningMode.FIXED_TIME.value,
                "09:30:00",
                None,
                None,
                "2025-11-05 09:29:59",
                True,
            ),
            (
                const.MorningOpeningMode.FIXED_TIME.value,
                "09:30:00",
                None,
                None,
                "2025-11-05 09:30:00",
                False,
            ),
            (
                const.MorningOpeningMode.RELATIVE_TO_SUNRISE.value,
                "00:30:00",
                None,
                (7, 0, 0),
                "2025-11-05 07:29:59",
                True,
            ),
            (
                const.MorningOpeningMode.RELATIVE_TO_SUNRISE.value,
                "00:30:00",
                None,
                (7, 0, 0),
                "2025-11-05 07:30:00",
                False,
            ),
            (
                const.MorningOpeningMode.EXTERNAL.value,
                None,
                "08:15:00",
                None,
                "2025-11-05 08:14:59",
                True,
            ),
            (
                const.MorningOpeningMode.EXTERNAL.value,
                None,
                "08:15:00",
                None,
                "2025-11-05 08:15:00",
                False,
            ),
        ],
        ids=[
            "fixed-before-cutoff",
            "fixed-at-cutoff",
            "relative-before-cutoff",
            "relative-at-cutoff",
            "external-before-cutoff",
            "external-at-cutoff",
        ],
    )
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_morning_opening_matrix_releases_carryover_at_resolved_cutoff(
        self,
        mock_get_astral,
        mock_ha_interface,
        mock_logger,
        freezer,
        morning_mode,
        morning_time,
        external_time,
        sunrise_time,
        now_string,
        expected,
    ):
        """Test carryover boundaries across the supported morning opening modes."""

        from datetime import datetime

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: const.EveningClosureMode.FIXED_TIME.value,
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
            ConfKeys.MORNING_OPENING_MODE.value: morning_mode,
        }
        if morning_time is not None:
            config[ConfKeys.MORNING_OPENING_TIME.value] = morning_time
        if external_time is not None:
            config[const.TIME_KEY_MORNING_OPENING_EXTERNAL_TIME] = external_time

        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        if sunrise_time is not None:
            hour, minute, second = sunrise_time
            mock_get_astral.return_value = datetime(
                2025,
                11,
                5,
                hour,
                minute,
                second,
                tzinfo=dt_util.get_default_time_zone(),
            )
        else:
            mock_get_astral.return_value = None

        freezer.move_to(now_string)

        assert engine._compute_post_evening_closure() is expected

    def test_fixed_morning_opening_keeps_block_until_time(self, mock_ha_interface, mock_logger, freezer):
        """Test that fixed morning opening keeps the block active until the configured time."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
            ConfKeys.MORNING_OPENING_MODE.value: "fixed_time",
            ConfKeys.MORNING_OPENING_TIME.value: "09:30:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        freezer.move_to("2025-11-05 08:00:00")
        assert engine._compute_post_evening_closure() is True

        freezer.move_to("2025-11-05 10:00:00")
        assert engine._compute_post_evening_closure() is False

    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_relative_morning_opening_matches_sunrise_by_default(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that relative morning opening with zero delay releases at sunrise."""

        from datetime import datetime

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
            ConfKeys.MORNING_OPENING_MODE.value: "relative_to_sunrise",
            ConfKeys.MORNING_OPENING_TIME.value: "00:00:00",
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        sunrise = datetime(2025, 11, 5, 7, 0, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunrise

        freezer.move_to("2025-11-05 06:30:00")
        assert engine._compute_post_evening_closure() is True

        freezer.move_to("2025-11-05 07:30:00")
        assert engine._compute_post_evening_closure() is False

    def test_missing_morning_opening_keeps_block_until_today_evening_closure(self, mock_ha_interface, mock_logger, freezer):
        """Test missing morning opening keeps the carryover block active until today's close time."""
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
            ConfKeys.MORNING_OPENING_MODE.value: "external",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-05 08:00:00")

        assert engine._compute_post_evening_closure() is True

    def test_missing_morning_opening_keeps_block_when_today_evening_closure_unavailable(self, mock_ha_interface, mock_logger, freezer):
        """Test missing morning opening keeps the carryover block active when today's close time is unavailable."""
        from datetime import datetime

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
            ConfKeys.MORNING_OPENING_MODE.value: "external",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-05 08:00:00")
        yesterday_closure = datetime(2025, 11, 4, 21, 0, 0, tzinfo=dt_util.get_default_time_zone())

        with (
            patch.object(engine, "_get_morning_opening_time_for_date", return_value=None),
            patch.object(
                engine,
                "_get_evening_closure_time_for_date",
                side_effect=[yesterday_closure, None, None],
            ),
        ):
            assert engine._compute_post_evening_closure() is True

    def test_missing_morning_opening_releases_block_after_today_evening_closure(self, mock_ha_interface, mock_logger, freezer):
        """Test missing morning opening does not keep the carryover block past today's evening closure."""
        from datetime import datetime

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
            ConfKeys.MORNING_OPENING_MODE.value: "external",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-05 21:05:00")
        yesterday_closure = datetime(2025, 11, 4, 21, 0, 0, tzinfo=dt_util.get_default_time_zone())
        today_closure = datetime(2025, 11, 5, 21, 0, 0, tzinfo=dt_util.get_default_time_zone())

        with (
            patch.object(engine, "_get_morning_opening_time_for_date", return_value=None),
            patch.object(
                engine,
                "_get_evening_closure_time_for_date",
                side_effect=[yesterday_closure, today_closure, today_closure],
            ),
        ):
            assert engine._compute_post_evening_closure() is True

    def test_post_evening_closure_returns_false_without_yesterday_or_today_closure(self, mock_ha_interface, mock_logger, freezer):
        """Test post-evening-closure stays false when no closure window exists to carry over."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_MODE.value: "fixed_time",
            ConfKeys.EVENING_CLOSURE_TIME.value: "21:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
            ConfKeys.MORNING_OPENING_MODE.value: "external",
        }
        resolved = resolve(config)
        engine = AutomationEngine(
            resolved=resolved,
            config=config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        freezer.move_to("2025-11-04 20:30:00")

        with (
            patch.object(engine, "_get_morning_opening_time_for_date", return_value=None),
            patch.object(engine, "_get_evening_closure_time_for_date", return_value=None),
        ):
            assert engine._compute_post_evening_closure() is False

    #
    # test_check_sunset_closing_inside_window_already_closed
    #
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_check_sunset_closing_inside_window_already_closed(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that method returns False if already closed within the window."""
        from datetime import datetime

        # Setup
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        # Pre-set already closed
        engine._evening_covers_closed = True

        # Freeze time inside window
        freezer.move_to("2025-11-04 18:50:00")

        # Mock sunset
        sunset_time = datetime(2025, 11, 4, 18, 30, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunset_time

        result = engine._check_evening_closure()
        assert result is False

    #
    # test_check_sunset_closing_after_window_resets_state
    #
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_check_sunset_closing_after_window_resets_state(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that state resets after the closing window ends."""
        from datetime import datetime

        # Setup
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        # Pre-set state as already closed
        engine._evening_covers_closed = True

        # Freeze time to after window ends (window was 18:45-18:55, now it's 19:00)
        freezer.move_to("2025-11-04 19:00:00")

        # Mock sunset at 18:30
        sunset_time = datetime(2025, 11, 4, 18, 30, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunset_time

        result = engine._check_evening_closure()

        assert result is False
        assert engine._evening_covers_closed is False  # State reset

    #
    # test_check_sunset_closing_zero_delay
    #
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_check_sunset_closing_zero_delay(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that zero delay triggers at sunset time."""
        from datetime import datetime

        # Setup with zero delay
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:00:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        # Freeze time to exactly sunset + 1 minute (inside window: 18:30 to 18:40)
        freezer.move_to("2025-11-04 18:31:00")

        # Mock sunset at 18:30
        sunset_time = datetime(2025, 11, 4, 18, 30, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunset_time

        result = engine._check_evening_closure()
        assert result is True

    #
    # test_check_sunset_closing_sunset_unavailable
    #
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_check_sunset_closing_sunset_unavailable(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that method returns False when sunset time is unavailable."""

        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        freezer.move_to("2025-11-04 18:45:00")

        # Mock sunset unavailable
        mock_get_astral.return_value = None

        result = engine._check_evening_closure()
        assert result is False

    #
    # test_check_sunset_closing_multiple_day_cycles
    #
    @patch("custom_components.smart_cover_automation.automation_engine.get_astral_event_date")
    def test_check_sunset_closing_multiple_day_cycles(self, mock_get_astral, mock_ha_interface, mock_logger, freezer):
        """Test that feature works correctly across multiple days."""
        from datetime import datetime

        # Setup
        config = {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_TIME.value: "00:15:00",
            ConfKeys.EVENING_CLOSURE_COVER_LIST.value: ["cover.test"],
        }
        resolved = resolve(config)
        engine = AutomationEngine(resolved=resolved, config=config, ha_interface=mock_ha_interface, logger=mock_logger)

        # Day 1: Inside window - should close
        freezer.move_to("2025-11-04 18:46:00")
        sunset_day1 = datetime(2025, 11, 4, 18, 30, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunset_day1

        result = engine._check_evening_closure()
        assert result is True
        assert engine._evening_covers_closed is True

        # Day 1: After window - should reset
        freezer.move_to("2025-11-04 19:00:00")
        result = engine._check_evening_closure()
        assert result is False
        assert engine._evening_covers_closed is False

        # Day 2: Inside new window - should close again
        freezer.move_to("2025-11-05 18:47:00")
        sunset_day2 = datetime(2025, 11, 5, 18, 31, 0, tzinfo=dt_util.get_default_time_zone())
        mock_get_astral.return_value = sunset_day2

        result = engine._check_evening_closure()
        assert result is True
