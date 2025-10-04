"""Implementation of the automation logic."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_POSITION, CoverEntityFeature
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator as BaseCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import const
from .config import ConfKeys, ResolvedConfig, resolve_entry
from .util import to_float_or_none

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
class DataUpdateCoordinator(BaseCoordinator[dict[str, Any]]):
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
        resolved = resolve_entry(config_entry)
        const.LOGGER.info(
            f"Initializing {const.INTEGRATION_NAME} coordinator: covers={tuple(resolved.covers)}, update_interval={const.UPDATE_INTERVAL}"
        )

        # Initialize position history storage (non-persistent)
        # Dictionary structure: {entity_id: deque()}
        # Stores the last COVER_POSITION_HISTORY_SIZE positions for each cover using a deque for efficient operations
        self._cover_position_history: dict[str, deque[int | None]] = {}

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
        """Return resolved settings from the config entry (options over data)."""
        return resolve_entry(self.config_entry)

    #
    # _update_cover_position_history
    #
    def _update_cover_position_history(self, entity_id: str, new_position: int | None) -> None:
        """Update position history for a cover, maintaining the last COVER_POSITION_HISTORY_SIZE positions.

        Args:
            entity_id: The cover entity ID
            new_position: The new position to add to history
        """
        if entity_id not in self._cover_position_history:
            # First time seeing this cover - initialize with this position
            self._cover_position_history[entity_id] = deque([new_position], maxlen=const.COVER_POSITION_HISTORY_SIZE)
            const.LOGGER.debug(f"[{entity_id}] Initialized position history: {list(self._cover_position_history[entity_id])}")
        else:
            # Add new position to the front of the deque (most recent first)
            # The deque will automatically remove the oldest position when it exceeds maxlen
            history = self._cover_position_history[entity_id]
            history.appendleft(new_position)

            const.LOGGER.debug(
                f"[{entity_id}] Updated position history: {list(history)} (current: {history[0] if history else 'N/A'}, previous: {history[1] if len(history) > 1 else 'N/A'})"
            )

    #
    # _get_cover_position_history
    #
    def _get_cover_position_history(self, entity_id: str) -> dict[str, int | None | list[int | None]]:
        """Get the position history for a cover.

        Args:
            entity_id: The cover entity ID

        Returns:
            Dictionary with position history using const attribute names
        """
        history = self._cover_position_history.get(entity_id, deque())
        history_list = list(history)  # Convert deque to list for serialization
        return {
            const.COVER_ATTR_POS_HISTORY_ALL: history_list,  # All positions in order from newest to oldest
        }

    #
    # _async_update_data
    #
    async def _async_update_data(self) -> dict[str, Any]:
        """Update automation state and control covers.

        This is the heart of the automation logic. It evaluates sensor states and
        controls covers as needed.

        This is called by HA in the following cases:
        - First refresh
        - Periodically at update_interval
        - Manual refresh
        - Integration reload

        Returns:
        Dict that stores details of the last automation run.
        Dict entries are converted to HA entity attributes which are visible
        in the integration's automation sensor.

        Raises:
        UpdateFailed: For critical errors that should make entities unavailable
        """
        # Prepare minimal valid state to keep integration entities available
        error_result: dict[str, Any] = {ConfKeys.COVERS.value: {}}

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
                self._log_automation_result(message, const.LogSeverity.WARNING, error_result)
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

        finally:
            const.LOGGER.info("Finished cover automation update")

    #
    # _handle_automation
    #
    async def _handle_automation(
        self,
        states: dict[str, State | None],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Implements the automation logic.

        Called by _async_update_data after initial checks and state collection.
        """
        # Prepare empty result
        result: dict[str, Any] = {ConfKeys.COVERS.value: {}}

        # Get the resolved settings
        resolved = self._resolved_settings()

        # Temperature & sunshine input
        temp_threshold = resolved.temp_threshold
        weather_entity_id = resolved.weather_entity_id
        temp_max = await self._get_max_temperature(weather_entity_id)
        weather_condition = self._get_weather_condition(weather_entity_id)

        # Temperature above threshold?
        temp_hot = False
        if temp_max > temp_threshold:
            temp_hot = True

        # Sun shining?
        weather_sunny = False
        if weather_condition.lower() in const.WEATHER_SUNNY_CONDITIONS:
            weather_sunny = True

        # Cover settings
        covers_min_position_delta = resolved.covers_min_position_delta

        # Sun entity
        sun_elevation_threshold = resolved.sun_elevation_threshold
        sun_state = self.hass.states.get(const.HA_SUN_ENTITY_ID)
        if sun_state is None:
            # Required sun entity missing. This is a critical error.
            raise SunSensorNotFoundError(const.HA_SUN_ENTITY_ID)

        # Sun azimuth & elevation
        sun_elevation = to_float_or_none(sun_state.attributes.get(const.HA_SUN_ATTR_ELEVATION))
        if sun_elevation is None:
            message = "Sun elevation unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return result
        sun_azimuth = to_float_or_none(sun_state.attributes.get(const.HA_SUN_ATTR_AZIMUTH, 0))
        if sun_azimuth is None:
            message = "Sun azimuth unavailable; skipping actions"
            self._log_automation_result(message, const.LogSeverity.WARNING, result)
            return result

        # Store sensor attributes
        result.update(
            {
                const.SENSOR_ATTR_SUN_AZIMUTH: sun_azimuth,
                const.SENSOR_ATTR_SUN_ELEVATION: sun_elevation,
                const.SENSOR_ATTR_TEMP_CURRENT_MAX: temp_max,
                const.SENSOR_ATTR_TEMP_HOT: temp_hot,
                const.SENSOR_ATTR_WEATHER_SUNNY: weather_sunny,
            }
        )

        # Copy result without covers for logging
        result_copy = {k: v for k, v in result.items() if k != ConfKeys.COVERS.value}
        const.LOGGER.info(f"Calculated sensor states: {str(result_copy)}")

        # Iterate over covers
        const.LOGGER.debug("Starting cover evaluation")
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
                # Close the cover (but respect max closure limit)
                target_desired_pos = max(const.COVER_POS_FULLY_CLOSED, resolved.covers_max_closure)
            else:
                # Open the cover (but respect min closure limit)
                target_desired_pos = min(const.COVER_POS_FULLY_OPEN, resolved.covers_min_closure)
            cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = target_desired_pos

            # Determine if cover movement is necessary
            movement_needed = False
            if target_desired_pos == current_pos:
                message = "No movement needed"
            elif abs(target_desired_pos - current_pos) < covers_min_position_delta:
                message = "Skipping minor adjustment"
            else:
                message = "Moving cover"
                movement_needed = True

            if movement_needed:
                try:
                    # Move the cover
                    actual_pos = await self._set_cover_position(entity_id, target_desired_pos, features)
                    const.LOGGER.debug(f"[{entity_id}] Cover moved to position: {actual_pos}%")
                    if actual_pos is not None:
                        # Store the position after movement
                        cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = actual_pos
                        # Update position history for this cover
                        self._update_cover_position_history(entity_id, actual_pos)
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
                # No movement - just update position history with current position
                self._update_cover_position_history(entity_id, current_pos)

            # Include position history in cover attributes
            position_history = self._get_cover_position_history(entity_id)
            cover_attrs[const.COVER_ATTR_POS_HISTORY_ALL] = position_history[const.COVER_ATTR_POS_HISTORY_ALL]

            # Store per-cover attributes
            result[ConfKeys.COVERS.value][entity_id] = cover_attrs

            # Log per-cover attributes
            const.LOGGER.debug(f"[{entity_id}] {message} {str(cover_attrs)}")

        const.LOGGER.debug("Finished cover evaluation")

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
            if features & CoverEntityFeature.SET_POSITION:
                # The cover supports setting a specific position
                service = SERVICE_SET_COVER_POSITION
                service_data = {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: desired_pos}
                actual_position = desired_pos  # For position-supporting covers, actual equals desired
                const.LOGGER.debug(f"[{entity_id}] Using set_position service to move to {desired_pos}%")
            else:
                # Fallback to open/close - determine actual position based on service used
                if desired_pos > const.COVER_POS_FULLY_OPEN / 2:
                    service = SERVICE_OPEN_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_position = const.COVER_POS_FULLY_OPEN  # Binary covers go to fully open
                    const.LOGGER.debug(f"[{entity_id}] Using open_cover service (no position support)")
                else:
                    service = SERVICE_CLOSE_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_position = const.COVER_POS_FULLY_CLOSED  # Binary covers go to fully closed
                    const.LOGGER.debug(f"[{entity_id}] Using close_cover service (no position support)")

            resolved = self._resolved_settings()
            if resolved.simulating:
                # If simulation mode is enabled, skip the actual service call
                const.LOGGER.info(
                    f"[{entity_id}] Simulation mode enabled; skipping actual {service} call; would have moved to {actual_position}%"
                )
            else:
                # Call the service
                await self.hass.services.async_call(Platform.COVER, service, service_data)

            # Return the actual position that the cover was moved to
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
        if features & CoverEntityFeature.SET_POSITION:
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
        const.LOGGER.debug(f"Current weather condition from {entity_id}: {condition}")
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
            response = await self.hass.services.async_call(Platform.WEATHER, SERVICE_GET_FORECASTS, service_data, return_response=True)

            # Extract today's forecast data with proper type checking
            if not (response and isinstance(response, dict) and entity_id in response):
                const.LOGGER.debug(f"Invalid or empty forecast response for {entity_id}")
                return None

            entity_data = response[entity_id]
            if not (isinstance(entity_data, dict) and "forecast" in entity_data):
                const.LOGGER.debug(f"Forecast data missing in response for {entity_id}")
                return None

            forecast_list = entity_data["forecast"]
            if not (isinstance(forecast_list, list) and forecast_list):
                const.LOGGER.debug(f"Forecast list is empty or not a list for {entity_id}")
                return None

            # Find today's forecast and extract the max temperature
            today_forecast = self._find_today_forecast(forecast_list)
            if today_forecast:
                max_temp = self._extract_max_temperature(today_forecast)
                if max_temp is not None:
                    const.LOGGER.debug(f"Using forecast max temperature: {max_temp}°C from {entity_id}")
                    return max_temp

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
    # _find_today_forecast
    #
    def _find_today_forecast(self, forecast_list: list[Any]) -> dict[str, Any] | None:
        """Find today's forecast from the forecast list.

        Attempts to find today's forecast by checking the datetime field.
        Falls back to first entry if no datetime matching is possible.

        Args:
            forecast_list: List of forecast dictionaries

        Returns:
            Today's forecast dictionary or None if not found
        """
        if not forecast_list:
            return None

        # Get today's date for comparison
        today = datetime.now(timezone.utc).date()

        # Try to find forecast entry for today by datetime
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

                if forecast_date == today:
                    const.LOGGER.debug(f"Found today's forecast by date match: {datetime_field}")
                    return forecast

            except (ValueError, TypeError, AttributeError) as err:
                const.LOGGER.debug(f"Could not parse forecast datetime '{datetime_field}': {err}")
                continue

        # Fallback: use first entry and log the assumption
        const.LOGGER.debug("Could not find today's forecast by date, using first entry as fallback")
        first_forecast = forecast_list[0]
        return first_forecast if isinstance(first_forecast, dict) else None

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
            "temp_max",  # Alternative naming used by some integrations
            "temphigh",  # Alternative naming used by some integrations
        ]

        for field in temp_fields:
            if field in forecast:
                temp_value = forecast[field]
                if isinstance(temp_value, (int, float)):
                    const.LOGGER.debug(f"Extracted temperature from field '{field}': {temp_value}°C")
                    return float(temp_value)

        const.LOGGER.debug(f"No temperature fields found in forecast. Available fields: {list(forecast.keys())}")
        return None

    #
    # _log_automation_result
    #
    def _log_automation_result(self, message: str, severity: const.LogSeverity, result: dict[str, Any]) -> None:
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
        result[const.SENSOR_ATTR_MESSAGE] = message

    #
    # _log_cover_result
    #
    def _log_cover_result(
        self,
        entity_id: str,
        error_description: str,
        cover_attrs: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Log and store the the result for one cover."""
        message = f"[{entity_id}] {error_description}"
        const.LOGGER.warning(message)
        cover_attrs[const.COVER_ATTR_MESSAGE] = message
        result[ConfKeys.COVERS.value][entity_id] = cover_attrs
