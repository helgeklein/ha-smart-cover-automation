"""Automation engine classes for cover control logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import const
from .config import ConfKeys, ResolvedConfig
from .cover_automation import CoverAutomation, SensorData
from .cover_position_history import CoverPositionHistoryManager
from .data import CoordinatorData
from .util import to_float_or_none

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State


class AutomationEngine:
    """Orchestrates a complete automation run across all covers."""

    def __init__(
        self,
        hass: HomeAssistant,
        resolved: ResolvedConfig,
        config: dict[str, Any],
        cover_pos_history_mgr: CoverPositionHistoryManager,
        get_max_temperature_callback: Any,
        get_weather_condition_callback: Any,
        log_automation_result_callback: Any,
        log_cover_result_callback: Any,
        nighttime_check_callback: Any,
        time_period_check_callback: Any,
        set_cover_position_callback: Any,
        add_logbook_entry_callback: Any,
    ) -> None:
        """Initialize the automation engine.

        Args:
            hass: Home Assistant instance
            resolved: Resolved configuration settings
            config: Raw configuration dictionary
            cover_pos_history_mgr: Cover position history manager
            get_max_temperature_callback: Callback to get max temperature
            get_weather_condition_callback: Callback to get weather condition
            log_automation_result_callback: Callback to log automation results
            log_cover_result_callback: Callback to log cover results
            nighttime_check_callback: Callback to check nighttime block
            time_period_check_callback: Callback to check time period disable
            set_cover_position_callback: Callback to set cover position (entity_id, desired_pos, features) -> actual_pos
            add_logbook_entry_callback: Callback to add logbook entry (verb_key, entity_id, reason_key, target_pos)
        """

        self.hass = hass
        self.resolved = resolved
        self.config = config
        self._cover_pos_history_mgr = cover_pos_history_mgr
        self._get_max_temperature = get_max_temperature_callback
        self._get_weather_condition = get_weather_condition_callback
        self._log_automation_result = log_automation_result_callback
        self._log_cover_result = log_cover_result_callback
        self._nighttime_check = nighttime_check_callback
        self._time_period_check = time_period_check_callback
        self._set_cover_position = set_cover_position_callback
        self._add_logbook_entry = add_logbook_entry_callback

    async def run(self, cover_states: dict[str, State | None]) -> CoordinatorData:
        """Execute the automation logic for all covers.

        Args:
            cover_states: Dictionary mapping entity IDs to their states

        Returns:
            CoordinatorData with automation results
        """

        # Prepare empty result
        result: CoordinatorData = {ConfKeys.COVERS.value: {}}

        # Gather sensor data
        sensor_data = await self._gather_sensor_data(result)
        if sensor_data is None:
            # Critical data unavailable, result already logged
            return result

        # Store sensor data in result
        result["sun_azimuth"] = sensor_data.sun_azimuth
        result["sun_elevation"] = sensor_data.sun_elevation
        result["temp_current_max"] = sensor_data.temp_max
        result["temp_hot"] = sensor_data.temp_hot
        result["weather_sunny"] = sensor_data.weather_sunny

        # Log sensor states
        result_copy = {k: v for k, v in result.items() if k != ConfKeys.COVERS.value}
        const.LOGGER.info(f"Sensor states: {str(result_copy)}")

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
        if not self._check_global_conditions(result):
            return result

        # Process each cover
        for entity_id, state in cover_states.items():
            # Create a wrapper for logging that includes the result dict
            def log_cover_wrapper(ent_id: str, msg: str) -> None:
                self._log_cover_result(ent_id, msg)

            cover_automation = CoverAutomation(
                entity_id=entity_id,
                hass=self.hass,
                resolved=self.resolved,
                config=self.config,
                cover_pos_history_mgr=self._cover_pos_history_mgr,
                log_cover_result_callback=log_cover_wrapper,
                set_cover_position_callback=self._set_cover_position,
                add_logbook_entry_callback=self._add_logbook_entry,
            )
            cover_attrs = await cover_automation.process(state, sensor_data)
            if cover_attrs:
                result[ConfKeys.COVERS.value][entity_id] = cover_attrs

        return result

    async def _gather_sensor_data(self, result: CoordinatorData) -> SensorData | None:
        """Gather all sensor data needed for automation.

        Args:
            result: CoordinatorData to store messages in case of errors

        Returns:
            SensorData object or None if critical data is unavailable
        """
        # Get sun entity
        sun_entity = self.hass.states.get(const.HA_SUN_ENTITY_ID)
        if sun_entity is None:
            from .coordinator import SunSensorNotFoundError

            raise SunSensorNotFoundError(const.HA_SUN_ENTITY_ID)

        # Get sun azimuth & elevation
        sun_elevation = to_float_or_none(sun_entity.attributes.get(const.HA_SUN_ATTR_ELEVATION))
        if sun_elevation is None:
            message = "Sun elevation unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return None

        sun_azimuth = to_float_or_none(sun_entity.attributes.get(const.HA_SUN_ATTR_AZIMUTH, 0))
        if sun_azimuth is None:
            message = "Sun azimuth unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return None

        # Get weather data
        try:
            temp_max = await self._get_max_temperature(self.resolved.weather_entity_id)
            weather_condition = self._get_weather_condition(self.resolved.weather_entity_id)
        except Exception:  # Catches InvalidSensorReadingError, WeatherEntityNotFoundError
            message = "Weather data unavailable, skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return None

        # Calculate derived values
        temp_hot = temp_max > self.resolved.temp_threshold
        weather_sunny = weather_condition.lower() in const.WEATHER_SUNNY_CONDITIONS

        return SensorData(
            sun_azimuth=sun_azimuth,
            sun_elevation=sun_elevation,
            temp_max=temp_max,
            temp_hot=temp_hot,
            weather_condition=weather_condition,
            weather_sunny=weather_sunny,
        )

    def _check_global_conditions(self, result: CoordinatorData) -> bool:
        """Check global blocking conditions (nighttime, time ranges).

        Args:
            result: CoordinatorData to store messages

        Returns:
            True if automation should proceed, False if blocked
        """

        # Get sun entity for nighttime check
        sun_entity = self.hass.states.get(const.HA_SUN_ENTITY_ID)

        # Check nighttime block
        if self._nighttime_check(self.resolved, sun_entity):
            message = "It's nighttime and 'Disable cover opening at night' is enabled. Skipping actions"
            self._log_automation_result(message, const.LogSeverity.DEBUG, result)
            return False

        # Check time period disable
        in_disabled_period, period_string = self._time_period_check(self.resolved)
        if in_disabled_period:
            message = f"Automation is disabled for the current time period ({period_string}). Skipping actions"
            self._log_automation_result(message, const.LogSeverity.DEBUG, result)
            return False

        return True
