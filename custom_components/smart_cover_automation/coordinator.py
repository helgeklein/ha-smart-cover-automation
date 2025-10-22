"""Implementation of the automation logic."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_POSITION, CoverEntityFeature
from homeassistant.components.logbook import async_log_entry
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as ha_entity_registry
from homeassistant.helpers import translation
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator as BaseCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import const
from .config import ConfKeys, ResolvedConfig, resolve_entry
from .cover_position_history import CoverPositionHistoryManager
from .data import CoordinatorData
from .util import to_float_or_none, to_int_or_none

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

    from .data import IntegrationConfigEntry


#
# Exception classes
#
class SmartCoverError(UpdateFailed):
    """Base class for this integration's errors."""


class SunSensorNotFoundError(SmartCoverError):
    """Sun sensor could not be found."""

    def __init__(self, sensor_name: str) -> None:
        super().__init__(f"Sun sensor '{sensor_name}' not found")
        self.sensor_name = sensor_name


class WeatherEntityNotFoundError(SmartCoverError):
    """Temperature sensor could not be found."""

    def __init__(self, sensor_name: str) -> None:
        super().__init__(f"Temperature sensor '{sensor_name}' not found")
        self.sensor_name = sensor_name


class InvalidSensorReadingError(SmartCoverError):
    """Invalid sensor reading received."""

    def __init__(self, sensor_name: str, value: str) -> None:
        super().__init__(f"Invalid reading from '{sensor_name}': {value}")
        self.sensor_name = sensor_name
        self.value = value


class ServiceCallError(SmartCoverError):
    """Service call failed."""

    def __init__(self, service: str, entity_id: str, error: str) -> None:
        super().__init__(f"Failed to call {service} for {entity_id}: {error}")
        self.service = service
        self.entity_id = entity_id
        self.error = error


#
# DataUpdateCoordinator
#
class DataUpdateCoordinator(BaseCoordinator[CoordinatorData]):
    """Automation engine."""

    config_entry: IntegrationConfigEntry

    #
    # __init__
    #
    def __init__(self, hass: HomeAssistant, config_entry: IntegrationConfigEntry) -> None:
        super().__init__(
            hass,
            const.LOGGER,
            name=const.DOMAIN,
            update_interval=const.UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.config_entry = config_entry

        # Initialize position history manager
        self._cover_pos_history_mgr = CoverPositionHistoryManager()

        # Store merged config for comparison during reload
        self._merged_config: dict[str, Any] = {}

        # Store the unique_id of the status binary sensor (set by the sensor during __init__)
        # Used to look up the actual entity_id from the entity registry for logbook entries
        self.status_sensor_unique_id: str | None = None

        resolved = resolve_entry(config_entry)
        const.LOGGER.info(f"Initializing coordinator: update_interval={const.UPDATE_INTERVAL.total_seconds()} s")

        # Adjust log level if verbose logging is enabled
        try:
            if resolved.verbose_logging:
                const.LOGGER.setLevel(logging.DEBUG)
                const.LOGGER.debug("Verbose logging enabled")
        except Exception:
            pass

    #
    # _resolved_settings
    #
    def _resolved_settings(self) -> ResolvedConfig:
        """Return resolved settings from the config entry options."""
        from .config import resolve

        # Get configuration from options (all user settings are stored there)
        opts = dict(getattr(self.config_entry, const.HA_OPTIONS, {}) or {})

        return resolve(opts)

    #
    # _async_update_data
    #
    async def _async_update_data(self) -> CoordinatorData:
        """Update automation state and control covers.

        This is the heart of the automation logic. It evaluates sensor states and
        controls covers as needed.

        This is called by HA in the following cases:
        - First refresh
        - Periodically at update_interval
        - Manual refresh
        - Integration reload

        Returns:
        CoordinatorData that stores details of the last automation run.
        Data entries are converted to HA entity attributes which are visible
        in the integration's automation sensor.

        Raises:
        UpdateFailed: For critical errors that should make entities unavailable
        """
        # Prepare minimal valid state to keep integration entities available
        error_result: CoordinatorData = {ConfKeys.COVERS.value: {}}

        try:
            const.LOGGER.info("Starting cover automation update")

            # Keep a reference to raw config for dynamic per-cover direction
            config = self.config_entry.runtime_data.config

            # Get the resolved settings - configuration errors are critical
            try:
                resolved = self._resolved_settings()
            except Exception as err:
                # Configuration resolution failure is critical - entities should be unavailable
                const.LOGGER.error(f"Critical configuration error: {err}")
                raise UpdateFailed(f"Configuration error: {err}") from err

            # Get the configured covers
            covers = tuple(resolved.covers)
            if not covers:
                message = "No covers configured; skipping actions"
                self._log_automation_result(message, const.LogSeverity.INFO, error_result)
                return error_result

            # Get the enabled state
            enabled = resolved.enabled
            if not enabled:
                message = "Automation disabled via configuration; skipping actions"
                self._log_automation_result(message, const.LogSeverity.INFO, error_result)
                return error_result

            # Collect states for all configured covers
            states: dict[str, State | None] = {entity_id: self.hass.states.get(entity_id) for entity_id in covers}
            available_covers = sum(1 for s in states.values() if s is not None)
            if available_covers == 0:
                message = "All covers unavailable; skipping actions"
                self._log_automation_result(message, const.LogSeverity.INFO, error_result)
                return error_result

            # Run the automation logic
            return await self._handle_automation(states, config)

        except (SunSensorNotFoundError, WeatherEntityNotFoundError) as err:
            # Critical sensor errors - these make the automation non-functional
            const.LOGGER.error(f"Critical sensor error: {err}")
            raise UpdateFailed(str(err)) from err
        except UpdateFailed:
            # Re-raise other UpdateFailed exceptions (critical errors)
            raise
        except Exception as err:
            # Unexpected errors - log but continue operation to maintain system stability
            const.LOGGER.error(f"Unexpected error during automation update: {err}")
            const.LOGGER.debug(f"Exception details: {type(err).__name__}: {err}", exc_info=True)

            # For unexpected errors, return empty result to keep entities available
            # This prevents system instability from unknown issues
            return error_result

    #
    # _handle_automation
    #
    async def _handle_automation(
        self,
        states: dict[str, State | None],
        config: dict[str, Any],
    ) -> CoordinatorData:
        """Implements the automation logic.

        Called by _async_update_data after initial checks and state collection.
        """
        # Prepare empty result
        result: CoordinatorData = {ConfKeys.COVERS.value: {}}

        # Get the resolved settings
        resolved = self._resolved_settings()

        # Sun entity
        sun_elevation_threshold = resolved.sun_elevation_threshold
        sun_entity = self.hass.states.get(const.HA_SUN_ENTITY_ID)
        if sun_entity is None:
            # Required sun entity missing. This is a critical error.
            raise SunSensorNotFoundError(const.HA_SUN_ENTITY_ID)

        # Sun azimuth & elevation
        sun_elevation = to_float_or_none(sun_entity.attributes.get(const.HA_SUN_ATTR_ELEVATION))
        if sun_elevation is None:
            message = "Sun elevation unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return result
        sun_azimuth = to_float_or_none(sun_entity.attributes.get(const.HA_SUN_ATTR_AZIMUTH, 0))
        if sun_azimuth is None:
            message = "Sun azimuth unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return result

        # Weather
        weather_entity_id = resolved.weather_entity_id
        try:
            temp_max = await self._get_max_temperature(weather_entity_id)
            weather_condition = self._get_weather_condition(weather_entity_id)
        except (InvalidSensorReadingError, WeatherEntityNotFoundError):
            message = "Weather data unavailable, skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return result

        # Temperature above threshold?
        temp_threshold = resolved.temp_threshold
        temp_hot = False
        if temp_max > temp_threshold:
            temp_hot = True

        # Sun shining?
        weather_sunny = False
        if weather_condition.lower() in const.WEATHER_SUNNY_CONDITIONS:
            weather_sunny = True

        # Cover settings
        covers_min_position_delta = resolved.covers_min_position_delta

        # Store sensor attributes
        result["sun_azimuth"] = sun_azimuth
        result["sun_elevation"] = sun_elevation
        result["temp_current_max"] = temp_max
        result["temp_hot"] = temp_hot
        result["weather_sunny"] = weather_sunny

        # Copy result without covers for logging
        result_copy = {k: v for k, v in result.items() if k != ConfKeys.COVERS.value}
        const.LOGGER.info(f"Sensor states: {str(result_copy)}")

        # Log relevant global settings
        global_settings = {
            "temp_threshold": temp_threshold,
            "sun_elevation_threshold": sun_elevation_threshold,
            "sun_azimuth_tolerance": resolved.sun_azimuth_tolerance,
            "covers_min_position_delta": covers_min_position_delta,
            "weather_hot_cutover_time": resolved.weather_hot_cutover_time.strftime("%H:%M:%S"),
        }
        const.LOGGER.info(f"Global settings: {str(global_settings)}")

        # Nighttime?
        if self._nighttime_and_block_opening(resolved, sun_entity):
            message = "It's nighttime and 'Disable cover opening at night' is enabled. Skipping actions"
            self._log_automation_result(message, const.LogSeverity.DEBUG, result)
            return result

        # In automation disabled period?
        in_disabled_period, period_string = self._in_time_period_automation_disabled(resolved)
        if in_disabled_period:
            message = f"Automation is disabled for the current time period ({period_string}). Skipping actions"
            self._log_automation_result(message, const.LogSeverity.DEBUG, result)
            return result

        # Iterate over covers
        for entity_id, state in states.items():
            # Reset the per-cover attributes
            cover_attrs: dict[str, Any] = {}

            # Cover azimuth
            cover_azimuth_raw = config.get(f"{entity_id}_{const.COVER_SFX_AZIMUTH}")
            cover_azimuth = to_float_or_none(cover_azimuth_raw)
            if cover_azimuth is None:
                self._log_cover_result(entity_id, "Cover has invalid or missing azimuth (direction), skipping", cover_attrs, result)
                continue
            else:
                cover_attrs[const.COVER_ATTR_COVER_AZIMUTH] = cover_azimuth

            # Cover state
            if state is None or state.state is None:
                self._log_cover_result(entity_id, "Cover state unavailable, skipping", cover_attrs, result)
                continue
            elif state.state in ("", STATE_UNAVAILABLE, STATE_UNKNOWN):
                self._log_cover_result(entity_id, f"Cover state '{state.state}' unsupported, skipping", cover_attrs, result)
                continue
            else:
                cover_attrs[const.COVER_ATTR_STATE] = state.state

            # Check if cover is currently moving
            is_moving = state.state.lower() in (STATE_OPENING, STATE_CLOSING)
            if is_moving:
                self._log_cover_result(entity_id, "Cover is currently moving, skipping", cover_attrs, result)
                continue

            # Get cover features (e.g., SET_POSITION), defaulting to 0
            features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            cover_attrs[const.COVER_ATTR_SUPPORTED_FEATURES] = features

            # Get the current position
            current_pos = self._get_cover_position(entity_id, state, features)
            cover_attrs[const.COVER_ATTR_POS_CURRENT] = current_pos

            #
            # Check for manual override
            #
            # Get the last known cover position from history
            last_history_entry = self._cover_pos_history_mgr.get_latest_entry(entity_id)
            if last_history_entry is not None and current_pos != last_history_entry.position:
                # Position has changed since our last recorded desired position
                # Beware of system time changes
                time_now = datetime.now(timezone.utc)
                if time_now > last_history_entry.timestamp:
                    time_delta = (time_now - last_history_entry.timestamp).total_seconds()
                    if time_delta < resolved.manual_override_duration:
                        time_remaining = resolved.manual_override_duration - time_delta
                        message = f"Manual override detected (position changed externally), skipping this cover for another {time_remaining:.0f} s"
                        self._log_cover_result(entity_id, message, cover_attrs, result)
                        continue

            # Is the sun hitting the window?
            sun_hitting: bool = False
            sun_azimuth_difference = self._calculate_angle_difference(sun_azimuth, cover_azimuth)
            if sun_elevation >= sun_elevation_threshold:
                sun_hitting = sun_azimuth_difference < resolved.sun_azimuth_tolerance
            else:
                sun_hitting = False
            cover_attrs[const.COVER_ATTR_SUN_HITTING] = sun_hitting
            cover_attrs[const.COVER_ATTR_SUN_AZIMUTH_DIFF] = sun_azimuth_difference

            # Calculate the cover position
            if temp_hot and weather_sunny and sun_hitting:
                # Heat protection mode - close the cover

                # Get the max closure limit for this cover
                max_closure_limit = self._get_cover_closure_limit(entity_id, config, get_max=True)
                # Close the cover (but respect max closure limit)
                desired_pos = max(const.COVER_POS_FULLY_CLOSED, max_closure_limit)
                desired_pos_friendly_name = "heat protection state (closed)"
                verb_key = const.TRANSL_LOGBOOK_VERB_CLOSING
                reason_key = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION

            else:
                # "Let light in" mode - open the cover

                # Get the min closure limit for this cover
                min_closure_limit = self._get_cover_closure_limit(entity_id, config, get_max=False)
                # Open the cover (but respect min closure limit)
                desired_pos = min(const.COVER_POS_FULLY_OPEN, min_closure_limit)
                desired_pos_friendly_name = "normal state (open)"
                verb_key = const.TRANSL_LOGBOOK_VERB_OPENING
                reason_key = const.TRANSL_LOGBOOK_REASON_LET_LIGHT_IN

            # Store and log desired target position
            cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = desired_pos
            const.LOGGER.debug(f"[{entity_id}] Desired position: {desired_pos}%, {desired_pos_friendly_name}")

            # Determine if cover movement is necessary
            movement_needed = False
            if desired_pos == current_pos:
                message = "No movement needed"
            elif abs(desired_pos - current_pos) < covers_min_position_delta:
                message = "Skipped minor adjustment"
            else:
                message = "Moved cover"
                movement_needed = True

            if movement_needed:
                try:
                    # Move the cover
                    actual_pos = await self._set_cover_position(entity_id, desired_pos, features)
                    const.LOGGER.debug(f"[{entity_id}] Actual position: {actual_pos}%")
                    if actual_pos is not None:
                        # Store the position after movement
                        cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = actual_pos
                        # Add the new position to the history
                        self._cover_pos_history_mgr.add(entity_id, actual_pos, cover_moved=True)
                        # Add detailed logbook entry
                        await self._add_logbook_entry_cover_movement(
                            verb_key=verb_key,
                            entity_id=entity_id,
                            reason_key=reason_key,
                            target_pos=actual_pos,
                        )
                except ServiceCallError as err:
                    # Log the error but continue with other covers
                    const.LOGGER.error(f"[{entity_id}] Failed to control cover: {err}")
                    cover_attrs[const.COVER_ATTR_MESSAGE] = str(err)
                except (ValueError, TypeError) as err:
                    # Parameter validation errors
                    error_msg = f"Invalid parameters for cover control: {err}"
                    const.LOGGER.error(f"[{entity_id}] {error_msg}")
                    cover_attrs[const.COVER_ATTR_MESSAGE] = error_msg
            else:
                # No movement - just add the current position to the history
                self._cover_pos_history_mgr.add(entity_id, current_pos, cover_moved=False)

            # Include position history in cover attributes
            position_entries = self._cover_pos_history_mgr.get_entries(entity_id)
            cover_attrs[const.COVER_ATTR_POS_HISTORY] = [entry.position for entry in position_entries]

            # Store per-cover attributes
            result[ConfKeys.COVERS.value][entity_id] = cover_attrs

            # Log per-cover attributes
            const.LOGGER.debug(f"[{entity_id}] Cover result: {message}. Cover data: {str(cover_attrs)}")

        return result

    #
    # _set_cover_position
    #
    async def _set_cover_position(self, entity_id: str, desired_pos: int, features: int) -> int | None:
        """Set cover position using the most appropriate service call.

        Args:
            entity_id: The cover entity ID to control
            desired_pos: Target position (0-100, where 0=closed, 100=open)
            features: Cover's supported features bitmask

        Returns:
            The actual position to which the cover was moved (0-100, where 0=closed, 100=open)

        Raises:
            ServiceCallError: If the service call fails
            ValueError: If desired_pos is outside valid range (0-100)
        """

        # Validate position parameter
        if not (const.COVER_POS_FULLY_CLOSED <= desired_pos <= const.COVER_POS_FULLY_OPEN):
            raise ValueError(
                f"desired_pos must be between {const.COVER_POS_FULLY_CLOSED} and {const.COVER_POS_FULLY_OPEN}, got {desired_pos}"
            )

        # Initialize service name and actual position for error handling and return value
        service = "unknown_service"
        actual_position = None

        try:
            if int(features) & CoverEntityFeature.SET_POSITION:
                # The cover supports setting a specific position
                service = SERVICE_SET_COVER_POSITION
                service_data = {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: desired_pos}
                actual_position = desired_pos  # For position-supporting covers, actual equals desired
                const.LOGGER.debug(f"[{entity_id}] Moving to {desired_pos}% via set_position service")
            else:
                # Fallback to open/close - determine actual position based on service used
                if desired_pos > const.COVER_POS_FULLY_OPEN / 2:
                    service = SERVICE_OPEN_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_position = const.COVER_POS_FULLY_OPEN  # Binary covers go to fully open
                    const.LOGGER.debug(f"[{entity_id}] Opening fully via open_cover service (no position support)")
                else:
                    service = SERVICE_CLOSE_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_position = const.COVER_POS_FULLY_CLOSED  # Binary covers go to fully closed
                    const.LOGGER.debug(f"[{entity_id}] Closing fully via close_cover service (no position support)")

            resolved = self._resolved_settings()
            if resolved.simulation_mode:
                # If simulation mode is enabled, skip the actual service call
                const.LOGGER.info(
                    f"[{entity_id}] Simulation mode enabled; skipping actual {service} call; would have moved to {actual_position}%"
                )
            else:
                # Call the service (waiting until HA has processed it, but not waiting until the cover has finished moving)
                await self.hass.services.async_call(Platform.COVER, service, service_data)

            # Return the actual position the cover is moving to
            return actual_position

        except (OSError, ConnectionError, TimeoutError) as err:
            # Network/communication errors
            error_msg = f"Communication error while controlling cover: {err}"
            const.LOGGER.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

        except (ValueError, TypeError) as err:
            # Invalid parameters or data type issues
            error_msg = f"Invalid parameters for cover control: {err}"
            const.LOGGER.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

        except Exception as err:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error during cover control: {err}"
            const.LOGGER.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

    #
    # _get_cover_closure_limit
    #
    def _get_cover_closure_limit(self, entity_id: str, config: dict[str, Any], get_max: bool) -> int:
        """Get the min or max closure limit for a cover.

        Checks for per-cover override first, then falls back to global setting.

        Args:
            entity_id: The cover entity ID
            config: Raw configuration dictionary containing per-cover settings
            get_max: True to get max_closure limit, False to get min_closure limit

        Returns:
            The closure limit (0-100, where 0=closed, 100=open)
        """
        resolved = self._resolved_settings()

        if get_max:
            cover_suffix = const.COVER_SFX_MAX_CLOSURE
            limit_type = "max_closure"
        else:
            cover_suffix = const.COVER_SFX_MIN_CLOSURE
            limit_type = "min_closure"

        # Check for per-cover override
        per_cover_value = to_int_or_none(config.get(f"{entity_id}_{cover_suffix}"))
        if per_cover_value is not None:
            const.LOGGER.debug(f"[{entity_id}] Per-cover {limit_type} limit: {per_cover_value}%")
            return per_cover_value

        # Fall back to global setting
        if get_max:
            global_value = resolved.covers_max_closure
        else:
            global_value = resolved.covers_min_closure

        return global_value

    #
    # _get_cover_position
    #
    def _get_cover_position(self, entity_id: str, state: State, features: int) -> int:
        """Get the current position of a cover.

        For covers that support SET_POSITION, uses the current_position attribute.
        For binary covers (open/close only), determines position from the state.

        Args:
            entity_id: The cover entity ID for logging
            state: The cover's state object
            features: Cover's supported features bitmask

        Returns:
            Current position (0-100, where 0=closed, 100=open) or fully open if no position can be determined
        """
        # Default return value
        default_pos = const.COVER_POS_FULLY_OPEN

        # Check if cover supports position control
        if int(features) & CoverEntityFeature.SET_POSITION:
            # Cover supports positioning - use current_position attribute
            current_pos = state.attributes.get(ATTR_CURRENT_POSITION)
            if current_pos is None:
                const.LOGGER.warning(
                    f"[{entity_id}] Cover supports positioning but has no current_position attribute; defaulting to {default_pos}%"
                )
                return default_pos
            else:
                const.LOGGER.debug(f"[{entity_id}] Position-supporting cover at {current_pos}%")
                return int(current_pos)
        else:
            # Binary cover - determine position from state or fallback to current_position
            if state.state:
                cover_state = state.state.lower()
            else:
                cover_state = None

            if cover_state == STATE_CLOSED:
                const.LOGGER.debug(f"[{entity_id}] Binary cover is closed (0%)")
                return const.COVER_POS_FULLY_CLOSED
            elif cover_state == STATE_OPEN:
                const.LOGGER.debug(f"[{entity_id}] Binary cover is open (100%)")
                return const.COVER_POS_FULLY_OPEN
            else:
                const.LOGGER.warning(
                    f"[{entity_id}] Binary cover in state '{state.state}', cannot determine position; defaulting to {default_pos}%"
                )

        return default_pos

    # _get_weather_condition
    #
    def _get_weather_condition(self, entity_id: str) -> str:
        """Get the current weather condition from a weather entity.

        This method retrieves the current state of a weather entity, which represents
        the current weather condition (e.g., 'sunny', 'cloudy', 'rainy', etc.).

        Args:
            entity_id: Entity ID of the weather entity.

        Returns:
            The current weather condition as a string, or None if the entity
            doesn't exist or the state is unavailable.

        Raises:
            WeatherEntityNotFoundError: If the weather entity doesn't exist.
            InvalidSensorReadingError: If the state is unavailable or invalid.
        """
        state = self.hass.states.get(entity_id)
        if state is None:
            raise WeatherEntityNotFoundError(entity_id)

        if state.state in (None, "unavailable", "unknown"):
            raise InvalidSensorReadingError(entity_id, f"Weather entity {entity_id}: state is unavailable")

        condition = state.state
        const.LOGGER.debug(f"Current weather condition: {condition}")
        return condition

    #
    # _get_max_temperature
    #
    async def _get_max_temperature(self, entity_id: str) -> float:
        """Get today's maximum temperature value from a weather forecast.

        This method uses the weather forecast to get the maximum
        temperature for the current day.

        Args:
            entity_id: Entity ID of the weather entity.

        Returns:
            The forecasted maximum temperature in degrees Celsius.

        Raises:
            WeatherEntityNotFoundError: If the weather entity doesn't exist.
            InvalidSensorReadingError: If the forecast is unavailable or the
                                     temperature value cannot be parsed.
        """
        state = self.hass.states.get(entity_id)
        if state is None:
            raise WeatherEntityNotFoundError(entity_id)

        forecast_temp = await self._get_forecast_max_temp(entity_id)
        if forecast_temp is not None:
            return forecast_temp

        # If forecast is not available, raise an error
        raise InvalidSensorReadingError(entity_id, "Forecast temperature unavailable")

    #
    # _get_forecast_max_temp
    #
    async def _get_forecast_max_temp(self, entity_id: str) -> float | None:
        """Get the max temperature from today's weather forecast."""
        try:
            # Use the modern weather forecast service
            service_data = {"entity_id": entity_id, "type": "daily"}
            response = await self.hass.services.async_call(
                Platform.WEATHER, SERVICE_GET_FORECASTS, service_data, blocking=True, return_response=True
            )

            # Debug logging to understand the response structure
            const.LOGGER.debug(f"Weather forecast service response for {entity_id}: {response}")

            # Extract today's forecast data with proper type checking
            if not (response and isinstance(response, dict) and entity_id in response):
                const.LOGGER.warning(f"Invalid or empty forecast response for {entity_id}: {response}")
                return None

            entity_data = response[entity_id]
            if not (isinstance(entity_data, dict) and "forecast" in entity_data):
                const.LOGGER.warning(
                    f"Forecast data missing in response for {entity_id}. Available keys: {list(entity_data.keys()) if isinstance(entity_data, dict) else 'Not a dict'}"
                )
                return None

            forecast_list = entity_data["forecast"]
            if not (isinstance(forecast_list, list) and forecast_list):
                const.LOGGER.warning(
                    f"Forecast list is empty or not a list for {entity_id}: {type(forecast_list)} with length {len(forecast_list) if isinstance(forecast_list, list) else 'N/A'}"
                )
                return None

            # Find today's forecast and extract the max temperature
            applicable_day = day_forecast = None
            forecast_result = self._find_day_forecast(forecast_list)
            if forecast_result is None:
                return None
            else:
                applicable_day, day_forecast = forecast_result

            max_temp = self._extract_max_temperature(day_forecast)
            if max_temp is not None:
                const.LOGGER.debug(f"Forecast max temperature: {max_temp} °C for {applicable_day}")
                return max_temp
            else:
                const.LOGGER.warning(f"Could not extract max temperature from today's forecast for {entity_id}")

        except HomeAssistantError as err:
            const.LOGGER.warning(f"Failed to call weather forecast service for {entity_id}: {err}")
        except Exception as err:
            const.LOGGER.warning(f"Unexpected error getting weather forecast from {entity_id}: {err}")

        return None

    #
    # _calculate_angle_difference
    #
    def _calculate_angle_difference(self, sun_azimuth: float, cover_azimuth: float) -> float:
        """Calculate minimal absolute angle difference between two azimuths."""
        return abs(((sun_azimuth - cover_azimuth + 180) % 360) - 180)

    #
    # _find_day_forecast
    #
    def _find_day_forecast(self, forecast_list: list[Any]) -> tuple[str, dict[str, Any]] | None:
        """Find the applicable daily forecast from the forecast list.

        Attempts to find the applicable forecast by checking the datetime field.
        Before weather_hot_cutover_time (default 16:00), uses today's forecast;
        after cutover time, uses tomorrow's forecast for hot weather detection.

        Args:
            forecast_list: List of forecast dictionaries

        Returns:
            Applicable forecast dictionary or None if not found
        """
        if not forecast_list:
            const.LOGGER.warning("Forecast list is empty")
            return None

        # Get the cutover time from configuration
        resolved = self._resolved_settings()
        cutover_time = resolved.weather_hot_cutover_time

        # Determine which day's forecast to use based on current time in local timezone
        # Use Home Assistant's configured timezone for the cutover comparison
        now_local = dt_util.now()
        current_time = now_local.time()

        # If current time is after cutover time, use tomorrow's forecast
        if current_time >= cutover_time:
            applicable_day = (now_local + timedelta(days=1)).date()
            applicable_day_friendly = "tomorrow"
        else:
            applicable_day = now_local.date()
            applicable_day_friendly = "today"

        # Try to find forecast entry for applicable day by datetime
        for forecast in forecast_list:
            if not isinstance(forecast, dict):
                continue

            # Check common datetime field names
            datetime_field = forecast.get("datetime") or forecast.get("date")
            if not datetime_field:
                continue

            try:
                # Parse the datetime field
                if isinstance(datetime_field, str):
                    forecast_date = datetime.fromisoformat(datetime_field.replace("Z", "+00:00")).date()
                elif hasattr(datetime_field, "date"):
                    # Assume it's a datetime object
                    forecast_date = datetime_field.date()
                else:
                    continue

                if forecast_date == applicable_day:
                    return (applicable_day_friendly, forecast)

            except (ValueError, TypeError, AttributeError) as err:
                const.LOGGER.debug(f"Could not parse forecast datetime '{datetime_field}': {err}")
                continue

        # Fallback: use first entry and log the assumption
        const.LOGGER.warning("Could not find weather forecast by date")
        return None

    #
    # _extract_max_temperature
    #
    def _extract_max_temperature(self, forecast: dict[str, Any]) -> float | None:
        """Extract maximum temperature from forecast entry.

        Tries multiple common temperature field names in order of preference.

        Args:
            forecast: Forecast dictionary

        Returns:
            Maximum temperature value or None if not found
        """
        if not isinstance(forecast, dict):
            return None

        # Temperature field names in order of preference (based on official HA weather entity spec)
        temp_fields = [
            "native_temperature",  # Official HA field for higher/max temperature (required in forecasts)
            "temperature",  # Most common field name used by weather integrations
            "temp_max",  # Alternative naming used by some integrations
            "temp_high",  # Alternative naming used by some integrations
            "temphigh",  # Alternative naming used by some integrations
            "high",  # Simple naming used by some integrations
            "max_temp",  # Alternative naming used by some integrations
        ]

        for field_name in temp_fields:
            if field_name in forecast:
                temp_value = forecast[field_name]
                if isinstance(temp_value, (int, float)):
                    return float(temp_value)
                else:
                    const.LOGGER.debug(f"Field '{field_name}' is not a number: {temp_value}")

        const.LOGGER.warning(f"No temperature fields found in forecast. Available fields: {list(forecast.keys())}")
        return None

    #
    # _log_automation_result
    #
    def _log_automation_result(self, message: str, severity: const.LogSeverity, result: CoordinatorData) -> None:
        """Log and store the result of an automation run."""
        # Log the message
        if severity == const.LogSeverity.DEBUG:
            const.LOGGER.debug(message)
        elif severity == const.LogSeverity.INFO:
            const.LOGGER.info(message)
        elif severity == const.LogSeverity.WARNING:
            const.LOGGER.warning(message)
        else:
            const.LOGGER.error(message)

        # Record the message in the result
        result["message"] = message

    #
    # _log_cover_result
    #
    def _log_cover_result(
        self,
        entity_id: str,
        error_description: str,
        cover_attrs: dict[str, Any],
        result: CoordinatorData,
    ) -> None:
        """Log and store the the result for one cover."""
        message = f"[{entity_id}] {error_description}"
        const.LOGGER.info(message)
        cover_attrs[const.COVER_ATTR_MESSAGE] = message
        result[ConfKeys.COVERS.value][entity_id] = cover_attrs

    #
    # _add_logbook_entry_cover_movement
    #
    async def _add_logbook_entry_cover_movement(
        self,
        verb_key: str,
        entity_id: str,
        reason_key: str,
        target_pos: int,
    ) -> None:
        """Add a detailed logbook entry for cover movement.

        Associates the entry with the integration's status binary sensor so it appears
        when filtering the logbook by this integration's device.

        Uses the stored unique_id to look up the current entity_id from the registry,
        which handles cases where users have renamed the entity.

        Translates the message using the current language setting with English as fallback.
        The translation keys require an associated service to pass Hassfest validation.
        We don't actually use the service, though.
        """

        try:
            # Look up the entity ID from the entity registry using the stored unique_id
            # This handles entity renames correctly since unique_id never changes
            registry = ha_entity_registry.async_get(self.hass)
            unique_id = self.status_sensor_unique_id

            # Find the entity by unique_id
            integration_entity_id = None
            for entity in registry.entities.values():
                if entity.unique_id == unique_id and entity.platform == const.DOMAIN:
                    integration_entity_id = entity.entity_id
                    break

            if integration_entity_id is None:
                const.LOGGER.warning(f"Could not find integration entity for logbook entry by its unique_id: {unique_id}")
                return

            # Get translations for the current language.
            # HA falls back to English automatically if a translation is missing.
            translations = await translation.async_get_translations(
                self.hass,
                self.hass.config.language,
                const.TRANSL_KEY_SERVICES,
                [const.DOMAIN],
            )

            # Build translation keys
            base_fields_key = (
                f"component.{const.DOMAIN}.{const.TRANSL_KEY_SERVICES}.{const.SERVICE_LOGBOOK_ENTRY}.{const.TRANSL_KEY_FIELDS}"
            )
            verb_key = f"{base_fields_key}.{verb_key}.{const.TRANSL_ATTR_NAME}"
            reason_key = f"{base_fields_key}.{reason_key}.{const.TRANSL_ATTR_NAME}"
            template_key = f"{base_fields_key}.{const.TRANSL_LOGBOOK_TEMPLATE_COVER_MOVEMENT}.{const.TRANSL_ATTR_NAME}"

            # Get translated strings
            translated_verb = translations.get(verb_key)
            translated_reason = translations.get(reason_key)
            translated_template = translations.get(template_key)
            if translated_verb is None or translated_reason is None or translated_template is None:
                const.LOGGER.warning(
                    f"Missing translations for logbook entry: verb='{verb_key}', reason='{reason_key}', template='{template_key}'"
                )
                return

            # Build the message
            message = translated_template.format(
                verb=translated_verb,
                entity_id=entity_id,
                reason=translated_reason,
                position=target_pos,
            )

            # Add the logbook entry
            async_log_entry(
                self.hass,
                name=const.INTEGRATION_NAME,
                message=message,
                domain=const.DOMAIN,
                entity_id=integration_entity_id,
            )
        except Exception as err:
            # Don't fail the entire automation if logbook entry fails
            const.LOGGER.debug(f"[{entity_id}] Failed to add logbook entry: {err}")

    #
    # _nighttime_and_block_opening
    #
    def _nighttime_and_block_opening(self, resolved: ResolvedConfig, sun_entity: State) -> bool:
        """Check if we're currently in a time period where "Disable cover opening at night" should be applied.

        Args:
            resolved: Resolved configuration settings

        Returns:
            True if cover opening should be blocked, False otherwise
        """
        # Check if to be disabled during night time (sun below horizon)
        if resolved.nighttime_block_opening:
            if sun_entity and sun_entity.state == const.HA_SUN_STATE_BELOW_HORIZON:
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
