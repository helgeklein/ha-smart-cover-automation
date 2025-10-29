"""Automation engine classes for cover control logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import const
from .config import ConfKeys, ResolvedConfig
from .cover_automation import CoverAutomation, SensorData
from .cover_position_history import CoverPositionHistoryManager
from .data import CoordinatorData

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
    ) -> None:
        """Initialize the automation engine.

        Args:
            resolved: Resolved configuration settings
            config: Raw configuration dictionary
            ha_interface: Home Assistant interface for API interactions
        """

        self.resolved = resolved
        self.config = config
        self._cover_pos_history_mgr = CoverPositionHistoryManager()
        self._ha_interface = ha_interface

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
        result: CoordinatorData = {ConfKeys.COVERS.value: {}}

        # Check if covers are configured
        covers = tuple(self.resolved.covers)
        if not covers:
            message = "No covers configured; skipping actions"
            self._log_automation_result(message, const.LogSeverity.INFO, result)
            return result

        # Check if automation is enabled
        if not self.resolved.enabled:
            message = "Automation disabled via configuration; skipping actions"
            self._log_automation_result(message, const.LogSeverity.INFO, result)
            return result

        # Check if any covers are available
        cover_count_available = sum(1 for s in cover_states.values() if s is not None)
        if cover_count_available == 0:
            message = "All covers unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.INFO, result)
            return result

        # Gather sensor data
        sensor_data, message = await self._gather_sensor_data()
        if sensor_data is None:
            # Critical data unavailable, automation canceled
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return result

        # Store sensor data in result
        result["sun_azimuth"] = sensor_data.sun_azimuth
        result["sun_elevation"] = sensor_data.sun_elevation
        result["temp_current_max"] = sensor_data.temp_max
        result["temp_hot"] = sensor_data.temp_hot
        result["weather_sunny"] = sensor_data.weather_sunny

        # Log sensor states
        sensor_states = {k: v for k, v in result.items() if k != ConfKeys.COVERS.value}
        const.LOGGER.info(f"Sensor states: {str(sensor_states)}")

        # Log global settings
        global_settings = {
            "temp_threshold": self.resolved.temp_threshold,
            "sun_elevation_threshold": self.resolved.sun_elevation_threshold,
            "sun_azimuth_tolerance": self.resolved.sun_azimuth_tolerance,
            "covers_min_position_delta": self.resolved.covers_min_position_delta,
            "weather_hot_cutover_time": self.resolved.weather_hot_cutover_time.strftime("%H:%M:%S"),
        }
        const.LOGGER.info(f"Global settings: {str(global_settings)}")

        # Check global blocking conditions
        success, message, severity = self._check_global_conditions()
        if not success:
            self._log_automation_result(message, severity, result)
            return result

        # Process each cover
        for entity_id, state in cover_states.items():
            cover_automation = CoverAutomation(
                entity_id=entity_id,
                resolved=self.resolved,
                config=self.config,
                cover_pos_history_mgr=self._cover_pos_history_mgr,
                ha_interface=self._ha_interface,
            )
            cover_attrs = await cover_automation.process(state, sensor_data)
            if cover_attrs:
                result[ConfKeys.COVERS.value][entity_id] = cover_attrs

        return result

    #
    # _gather_sensor_data
    #
    async def _gather_sensor_data(self) -> tuple[SensorData | None, str]:
        """Gather all sensor data needed for automation.

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
            const.LOGGER.error(f"Unexpected error getting sun data: {err}")
            return (None, f"Unexpected error getting sun data: {err}")

        # Get weather data
        try:
            temp_max = await self._ha_interface.get_max_temperature(self.resolved.weather_entity_id)
            weather_condition = self._ha_interface.get_weather_condition(self.resolved.weather_entity_id)
        except (InvalidSensorReadingError, WeatherEntityNotFoundError):
            return (None, "Weather data unavailable, skipping actions")
        except Exception as err:
            # Unexpected error - log and treat as temporary unavailability
            const.LOGGER.error(f"Unexpected error getting weather data: {err}")
            return (None, f"Unexpected error getting weather data: {err}")

        # Calculate derived values
        temp_hot = temp_max > self.resolved.temp_threshold
        weather_sunny = weather_condition.lower() in const.WEATHER_SUNNY_CONDITIONS

        return (
            SensorData(
                sun_azimuth=sun_azimuth,
                sun_elevation=sun_elevation,
                temp_max=temp_max,
                temp_hot=temp_hot,
                weather_condition=weather_condition,
                weather_sunny=weather_sunny,
            ),
            "",
        )

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

        # Get sun entity for nighttime check
        sun_state = self._ha_interface.get_sun_state()

        # Check nighttime block
        if self._nighttime_and_block_opening(self.resolved, sun_state):
            message = "It's nighttime and 'Disable cover opening at night' is enabled. Skipping actions"
            return (False, message, const.LogSeverity.DEBUG)

        # Check time period disable
        in_disabled_period, period_string = self._in_time_period_automation_disabled(self.resolved)
        if in_disabled_period:
            message = f"Automation is disabled for the current time period ({period_string}). Skipping actions"
            return (False, message, const.LogSeverity.DEBUG)

        return (True, "", const.LogSeverity.DEBUG)

    #
    # _nighttime_and_block_opening
    #
    def _nighttime_and_block_opening(self, resolved: ResolvedConfig, sun_state: str | None) -> bool:
        """Check if we're currently in a time period where "Disable cover opening at night" should be applied.

        Args:
            resolved: Resolved configuration settings
            sun_state: Sun state string (above_horizon or below_horizon), or None if unavailable

        Returns:
            True if cover opening should be blocked, False otherwise
        """

        # Check if to be disabled during night time (sun below horizon)
        if resolved.nighttime_block_opening:
            if sun_state == const.HA_SUN_STATE_BELOW_HORIZON:
                return True

        return False

    #
    # _in_time_period_automation_disabled
    #
    def _in_time_period_automation_disabled(self, resolved: ResolvedConfig) -> tuple[bool, str]:
        """Check if current time is within a period where the automation should be disabled.

        Args:
            resolved: Resolved configuration settings

        Returns:
            Tuple of (is_disabled, formatted_period_string) where:
            - is_disabled: True if we're in a disabled period, False otherwise
            - formatted_period_string: String like "22:00:00 - 06:00:00" or empty string if not in disabled period
        """

        from homeassistant.util import dt as dt_util

        # Get current local time
        now_local = dt_util.now().time()

        # Check if disabled the automation during custom time range is configured
        if not resolved.automation_disabled_time_range:
            return (False, "")

        # Get the start and end times
        period_start = resolved.automation_disabled_time_range_start
        period_end = resolved.automation_disabled_time_range_end

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
    def _log_automation_result(self, message: str, severity: const.LogSeverity, result: CoordinatorData) -> None:
        """Log the result of an automation run.

        Args:
            message: Message to log
            severity: Log severity level
            result: CoordinatorData (currently unused but kept for consistency)
        """
        # Log the message
        if severity == const.LogSeverity.DEBUG:
            const.LOGGER.debug(message)
        elif severity == const.LogSeverity.INFO:
            const.LOGGER.info(message)
        elif severity == const.LogSeverity.WARNING:
            const.LOGGER.warning(message)
        else:
            const.LOGGER.error(message)
