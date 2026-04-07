"""Automation engine classes for cover control logic."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from . import const
from .config import ResolvedConfig
from .cover_automation import CoverAutomation, SensorData
from .cover_position_history import CoverPositionHistoryManager
from .data import CoordinatorData
from .log import Log

if TYPE_CHECKING:
    from homeassistant.core import State


class AutomationEngine:
    """Abstracts the complete automation across all covers."""

    #
    # __init__
    #
    def __init__(
        self,
        resolved: ResolvedConfig,
        config: dict[str, Any],
        ha_interface: Any,
        logger: Log,
    ) -> None:
        """Initialize the automation engine.

        Args:
            resolved: Resolved configuration settings
            config: Raw configuration dictionary
            ha_interface: Home Assistant interface for API interactions
            logger: Instance-specific logger with entry_id prefix
        """

        self.resolved = resolved
        self.config = config
        self._cover_pos_history_mgr = CoverPositionHistoryManager()
        self._ha_interface = ha_interface
        self._logger = logger

        # First run tracking
        self._first_run: bool = True  # Track first iteration to suppress startup warnings

        # Evening closure state tracking
        self._evening_covers_closed: bool = False  # Prevent multiple closings within the evening closure window

    #
    # run
    #
    async def run(self, cover_states: dict[str, State | None]) -> CoordinatorData:
        """Execute the automation logic for all covers.

        Args:
            cover_states: Dictionary mapping entity IDs to their states

        Returns:
            CoordinatorData with automation results
        """

        # Prepare empty result
        result = CoordinatorData(covers={})

        # Track if this is first run (capture before clearing flag)
        is_first_run = self._first_run
        if self._first_run:
            self._first_run = False

        # Check if covers are configured
        covers = tuple(self.resolved.covers)
        if not covers:
            message = "No covers configured; skipping actions"
            self._log_automation_result(message, const.LogSeverity.INFO)
            return result

        # Check if automation is enabled
        if not self.resolved.enabled:
            message = "Automation disabled via configuration; skipping actions"
            self._log_automation_result(message, const.LogSeverity.INFO)
            return result

        # Check if any covers are available
        cover_count_available = sum(1 for s in cover_states.values() if s is not None)
        if cover_count_available == 0:
            message = "All covers unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.INFO)
            return result

        # Gather sensor data
        sensor_data, message = await self._gather_sensor_data(is_first_run)
        if sensor_data is None:
            # Critical data unavailable, automation canceled
            # Use DEBUG severity on first run to avoid startup warnings
            severity = const.LogSeverity.DEBUG if is_first_run else const.LogSeverity.WARNING
            self._log_automation_result(message, severity)
            return result

        # Get lock state
        lock_mode = self.resolved.lock_mode
        is_locked = lock_mode != const.LockMode.UNLOCKED

        # Store sensor data and lock state in result
        result.sun_azimuth = sensor_data.sun_azimuth
        result.sun_elevation = sensor_data.sun_elevation
        result.temp_current_max = sensor_data.temp_max
        result.temp_hot = sensor_data.temp_hot
        result.weather_sunny = sensor_data.weather_sunny

        # Log sensor states
        sensor_states = {
            "sun_azimuth": result.sun_azimuth,
            "sun_elevation": result.sun_elevation,
            "temp_current_max": result.temp_current_max,
            "temp_hot": result.temp_hot,
            "weather_sunny": result.weather_sunny,
        }
        self._logger.info(f"Sensor states: {str(sensor_states)}")

        # Log global settings
        global_settings = {
            "lock_mode": lock_mode,
            "covers_min_position_delta": self.resolved.covers_min_position_delta,
            "sun_azimuth_tolerance": self.resolved.sun_azimuth_tolerance,
            "sun_elevation_threshold": self.resolved.sun_elevation_threshold,
            "temp_threshold": self.resolved.temp_threshold,
            "weather_hot_cutover_time": self.resolved.weather_hot_cutover_time.strftime("%H:%M:%S"),
            "manual_override_duration": self.resolved.manual_override_duration,
            "automation_disabled_time_range": self.resolved.automation_disabled_time_range,
            "automation_disabled_time_range_start": self.resolved.automation_disabled_time_range_start.strftime("%H:%M:%S"),
            "automation_disabled_time_range_end": self.resolved.automation_disabled_time_range_end.strftime("%H:%M:%S"),
            "evening_closure_enabled": self.resolved.evening_closure_enabled,
            "evening_closure_mode": self.resolved.evening_closure_mode,
            "evening_closure_time": self.resolved.evening_closure_time.strftime("%H:%M:%S"),
            "evening_closure_ignore_manual_override_duration": self.resolved.evening_closure_ignore_manual_override_duration,
            "morning_opening_mode": self.resolved.morning_opening_mode,
            "morning_opening_time": self.resolved.morning_opening_time.strftime("%H:%M:%S"),
            "tilt_mode_day": self.resolved.tilt_mode_day,
            "tilt_mode_night": self.resolved.tilt_mode_night,
            "tilt_set_value_day": self.resolved.tilt_set_value_day,
            "tilt_set_value_night": self.resolved.tilt_set_value_night,
            "tilt_min_change_delta": self.resolved.tilt_min_change_delta,
            "tilt_slat_overlap_ratio": self.resolved.tilt_slat_overlap_ratio,
        }
        self._logger.info(f"Global settings: {str(global_settings)}")

        # Log lock state if active
        if is_locked:
            self._logger.warning(f"Cover lock active: {lock_mode}")

        # Check global blocking conditions
        success, message, severity = self._check_global_conditions()
        if not success:
            self._log_automation_result(message, severity)
            return result

        # Process each cover
        for entity_id, state in cover_states.items():
            cover_automation = CoverAutomation(
                entity_id=entity_id,
                resolved=self.resolved,
                config=self.config,
                cover_pos_history_mgr=self._cover_pos_history_mgr,
                ha_interface=self._ha_interface,
                logger=self._logger,
            )
            cover_attrs = await cover_automation.process(state, sensor_data)
            result.covers[entity_id] = cover_attrs

        return result

    #
    # _gather_sensor_data
    #
    async def _gather_sensor_data(self, is_first_run: bool = False) -> tuple[SensorData | None, str]:
        """Gather all sensor data needed for automation.

        Args:
            is_first_run: True if this is the first iteration after startup

        Returns:
            Tuple of (SensorData object or None if unavailable, error message if failed)
        """
        from .coordinator import SunSensorNotFoundError
        from .ha_interface import InvalidSensorReadingError, WeatherEntityNotFoundError

        # Get sun data
        try:
            sun_azimuth, sun_elevation = self._ha_interface.get_sun_data()
        except SunSensorNotFoundError:
            # SunSensorNotFoundError should propagate as it's critical
            raise
        except InvalidSensorReadingError as err:
            # InvalidSensorReadingError means sun data temporarily unavailable
            return (None, str(err))
        except Exception as err:
            # Unexpected error - log and treat as temporary unavailability
            self._logger.error(f"Unexpected error getting sun data: {err}")
            return (None, f"Unexpected error getting sun data: {err}")

        # Get weather data
        try:
            temp_max = await self._ha_interface.get_max_temperature(self.resolved.weather_entity_id)
            weather_condition = self._ha_interface.get_weather_condition(self.resolved.weather_entity_id)
        except InvalidSensorReadingError, WeatherEntityNotFoundError:
            message = (
                "Weather data unavailable on startup, skipping first iteration"
                if is_first_run
                else "Weather data unavailable, skipping actions"
            )
            return (None, message)
        except Exception as err:
            # Unexpected error - log and treat as temporary unavailability
            self._logger.error(f"Unexpected error getting weather data: {err}")
            return (None, f"Unexpected error getting weather data: {err}")

        # Calculate derived values
        temp_hot = temp_max > self.resolved.temp_threshold
        hot_source = "forecast threshold"

        weather_hot_external_control = self.config.get(const.SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL)
        if weather_hot_external_control is not None:
            temp_hot = bool(weather_hot_external_control)
            hot_source = "external control"

        # Check for weather sunny external control override
        weather_sunny_external_control = self.config.get(const.SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL)
        if weather_sunny_external_control is not None:
            # External control is enabled - use its boolean value to determine sunny state
            weather_sunny = bool(weather_sunny_external_control)
            sunny_source = "external control"
        else:
            # External control disabled - determine sunny state based on weather condition
            weather_sunny = weather_condition.lower() in const.WEATHER_SUNNY_CONDITIONS
            sunny_source = "weather entity"
        self._logger.debug(f"Current weather temperature state: {'hot' if temp_hot else 'not hot'} (source: {hot_source})")
        self._logger.debug(f"Current weather condition: {'sunny' if weather_sunny else 'not sunny'} (source: {sunny_source})")

        # Check for evening closure and handle delayed cover closing
        evening_closure = self._check_evening_closure()

        # Compute post-evening-closure flag for the opening block.
        # The cover logic applies it only to evening-closure covers.
        post_evening_closure = self._compute_post_evening_closure()

        return (
            SensorData(
                sun_azimuth=sun_azimuth,
                sun_elevation=sun_elevation,
                temp_max=temp_max,
                temp_hot=temp_hot,
                weather_condition=weather_condition,
                weather_sunny=weather_sunny,
                evening_closure=evening_closure,
                post_evening_closure=post_evening_closure,
            ),
            "",
        )

    #
    # _get_local_datetime_for_date
    #
    def _get_local_datetime_for_date(self, target_date: date, target_time: dt_time) -> datetime:
        """Return a timezone-aware local datetime for one date/time pair."""

        now = dt_util.now()
        return now.replace(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
            hour=target_time.hour,
            minute=target_time.minute,
            second=target_time.second,
            microsecond=0,
        )

    #
    # _get_evening_closure_time_for_date
    #
    def _get_evening_closure_time_for_date(self, target_date: date) -> datetime | None:
        """Calculate the evening closure time for one local date.

        Returns:
            The evening closure datetime for the requested date, or None if it cannot be
            determined (e.g. sunset data unavailable).
        """

        mode = self.resolved.evening_closure_mode

        if mode == const.EveningClosureMode.FIXED_TIME:
            closing_time = self.resolved.evening_closure_time
            return self._get_local_datetime_for_date(target_date, closing_time)

        # After sunset mode: sunset + configured delay
        sunset_time = get_astral_event_date(self._ha_interface.hass, SUN_EVENT_SUNSET, target_date)
        if sunset_time is None:
            self._logger.debug("Could not determine sunset time for %s", target_date.isoformat())
            return None

        delay_time = self.resolved.evening_closure_time
        delay_seconds = delay_time.hour * 3600 + delay_time.minute * 60 + delay_time.second
        return sunset_time + timedelta(seconds=delay_seconds)

    #
    # _get_evening_closure_time
    #
    def _get_evening_closure_time(self) -> datetime | None:
        """Calculate today's evening closure time based on the configured mode."""

        return self._get_evening_closure_time_for_date(dt_util.now().date())

    #
    # _get_morning_opening_time_for_date
    #
    def _get_morning_opening_time_for_date(self, target_date: date) -> datetime | None:
        """Calculate the morning opening time for one local date."""

        mode = self.resolved.morning_opening_mode

        if mode == const.MorningOpeningMode.FIXED_TIME:
            return self._get_local_datetime_for_date(target_date, self.resolved.morning_opening_time)

        if mode == const.MorningOpeningMode.EXTERNAL:
            external_time_raw = self.config.get(const.TIME_KEY_MORNING_OPENING_EXTERNAL_TIME)
            if external_time_raw is None:
                self._logger.debug("External morning opening mode active but no time is set")
                return None

            try:
                from .config import _Converters

                resolved_time = _Converters.to_time(external_time_raw)
            except AttributeError, TypeError, ValueError:
                self._logger.debug("Invalid external morning opening time: %r", external_time_raw)
                return None

            return self._get_local_datetime_for_date(target_date, resolved_time)

        sunrise_time = get_astral_event_date(self._ha_interface.hass, SUN_EVENT_SUNRISE, target_date)
        if sunrise_time is None:
            self._logger.debug("Could not determine sunrise time for %s", target_date.isoformat())
            return None

        delay_time = self.resolved.morning_opening_time
        delay_seconds = delay_time.hour * 3600 + delay_time.minute * 60 + delay_time.second
        return sunrise_time + timedelta(seconds=delay_seconds)

    #
    # _check_evening_closure
    #
    def _check_evening_closure(self) -> bool:
        """Check if covers should close based on evening closure settings.

        Supports two modes:
        - after_sunset: closes covers after sunset + configured delay
        - fixed_time: closes covers at a fixed time of day

        Uses a 10-minute window approach for reliability: covers should close if
        current time is within the window starting at the calculated closing time
        and ending 10 minutes later. This ensures we don't miss the closing even
        if an update cycle is skipped.

        Returns:
            True if covers should close now (first time in window), False otherwise
        """

        # Check if feature is enabled
        if not self.resolved.evening_closure_enabled:
            return False

        # Get current time and evening closure time
        now = dt_util.now()
        window_start = self._get_evening_closure_time()
        if window_start is None:
            return False

        window_end = window_start + timedelta(minutes=const.SUNSET_CLOSING_WINDOW_MINUTES)

        # Check if we're within the closing window
        in_window = window_start <= now < window_end

        if in_window:
            window_start_local = dt_util.as_local(window_start).strftime("%H:%M:%S")
            window_end_local = dt_util.as_local(window_end).strftime("%H:%M:%S")
            self._logger.info(f"Evening closure: In active time window ({window_start_local} - {window_end_local})")
            if not self._evening_covers_closed:
                # First time we've detected being in the window - close covers!
                self._evening_covers_closed = True
                self._logger.info("Evening closure: Signaling configured covers to be closed now")
                return True
        else:
            # Ensure the state is reset outside the window
            if self._evening_covers_closed:
                self._logger.debug("Evening closure: Outside active time window. Resetting state")
                self._evening_covers_closed = False

        return False

    #
    # _compute_post_evening_closure
    #
    def _compute_post_evening_closure(self) -> bool:
        """Determine whether we are past tonight's evening closure time.

        This flag is used by the "block opening after evening closure" feature
        to prevent covers from re-opening once the evening closure time has
        passed. It stays True until the configured morning opening time.

        The check is stateless — computed fresh every cycle:
        1. If evening closure is disabled → False
        2. If current time is still in the carryover block from yesterday evening → True
        3. If current time >= today's evening closure time → True
        4. Otherwise → False

        Returns:
            True if we are in the post-evening-closure period, False otherwise
        """

        # Evening closure must be enabled for this flag to apply
        if not self.resolved.evening_closure_enabled:
            return False

        now = dt_util.now()
        today = now.date()

        # Carryover from last night's evening closure until today's morning opening.
        evening_closure_yesterday = self._get_evening_closure_time_for_date(today - timedelta(days=1))
        morning_opening_today = self._get_morning_opening_time_for_date(today)
        if evening_closure_yesterday is not None:
            if morning_opening_today is None:
                evening_closure_today = self._get_evening_closure_time_for_date(today)
                if evening_closure_today is None or now < evening_closure_today:
                    return True
            elif evening_closure_yesterday <= now < morning_opening_today:
                return True

        evening_closure_time = self._get_evening_closure_time_for_date(today)
        if evening_closure_time is not None and now >= evening_closure_time:
            return True

        return False

    #
    # _check_global_conditions
    #
    def _check_global_conditions(self) -> tuple[bool, str, const.LogSeverity]:
        """Check global blocking conditions (nighttime, time ranges).

        Returns:
            Tuple of (should_proceed, block_message, severity) where:
            - should_proceed: True if automation should proceed, False if blocked
            - block_message: Error message if blocked, empty string otherwise
            - severity: Log severity level for the message
        """

        # Check time period disable
        in_disabled_period, period_string = self._in_time_period_automation_disabled()
        if in_disabled_period:
            message = f"Automation is disabled for the current time period ({period_string}). Skipping actions"
            return (False, message, const.LogSeverity.DEBUG)

        return (True, "", const.LogSeverity.DEBUG)

    #
    # _in_time_period_automation_disabled
    #
    def _in_time_period_automation_disabled(self) -> tuple[bool, str]:
        """Check if current time is within a period where the automation should be disabled.

        Args:
            resolved: Resolved configuration settings

        Returns:
            Tuple of (is_disabled, formatted_period_string) where:
            - is_disabled: True if we're in a disabled period, False otherwise
            - formatted_period_string: String like "22:00:00 - 06:00:00" or empty string if not in disabled period
        """

        # Get current local time
        now_local = dt_util.now().time()

        # Check if disabled the automation during custom time range is configured
        if not self.resolved.automation_disabled_time_range:
            return (False, "")

        # Get the start and end times
        period_start = self.resolved.automation_disabled_time_range_start
        period_end = self.resolved.automation_disabled_time_range_end

        # Are we in a disabled period?
        in_disabled_period = False
        if period_start < period_end:
            # Same day period (e.g., 09:00 to 17:00)
            if period_start <= now_local < period_end:
                in_disabled_period = True
        else:
            # Overnight period (e.g., 22:00 to 06:00)
            if now_local >= period_start or now_local < period_end:
                in_disabled_period = True

        if in_disabled_period:
            period_string = f"{period_start.strftime('%H:%M:%S')} - {period_end.strftime('%H:%M:%S')}"
            return (True, period_string)

        return (False, "")

    #
    # _log_automation_result
    #
    def _log_automation_result(self, message: str, severity: const.LogSeverity) -> None:
        """Log the result of an automation run.

        Args:
            message: Message to log
            severity: Log severity level
        """

        # Log the message
        if severity == const.LogSeverity.DEBUG:
            self._logger.debug(message)
        elif severity == const.LogSeverity.INFO:
            self._logger.info(message)
        elif severity == const.LogSeverity.WARNING:
            self._logger.warning(message)
        else:
            self._logger.error(message)
