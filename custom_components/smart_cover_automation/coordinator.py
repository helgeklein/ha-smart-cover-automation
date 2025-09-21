"""Implementation of the automation logic."""

from __future__ import annotations

import logging
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
        try:
            const.LOGGER.info("Starting cover automation update")

            # Prepare minimal valid state to keep integration entities available
            empty_result: dict[str, Any] = {ConfKeys.COVERS.value: {}}

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
                const.LOGGER.warning("No covers configured; skipping actions")
                return empty_result

            # Get the enabled state
            enabled = resolved.enabled
            if not enabled:
                const.LOGGER.info("Automation disabled via configuration; skipping actions")
                return empty_result

            # Collect states for all configured covers
            states: dict[str, State | None] = {entity_id: self.hass.states.get(entity_id) for entity_id in covers}
            available_covers = sum(1 for s in states.values() if s is not None)
            if available_covers == 0:
                const.LOGGER.error("All covers unavailable; skipping actions")
                return empty_result

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
            return empty_result

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
        temp_current = await self._get_max_temperature(weather_entity_id)
        weather_condition = self._get_weather_condition(weather_entity_id)

        # Temperature above threshold?
        temp_hot = False
        if temp_current > temp_threshold:
            temp_hot = True

        # Sun shining?
        weather_sunny = False
        if weather_condition.lower() in const.WEATHER_SUNNY_CONDITIONS:
            weather_sunny = True

        # Cover settings
        covers_min_position_delta = resolved.covers_min_position_delta

        # Sun input
        sun_elevation: float | None = None
        sun_azimuth: float | None = None
        sun_elevation_threshold = resolved.sun_elevation_threshold
        sun_sensor_entity_id = const.HA_SUN_ENTITY_ID
        sun_state = self.hass.states.get(sun_sensor_entity_id)
        if sun_state is None:
            # Required sun entity missing. This is a critical error.
            raise SunSensorNotFoundError(sun_sensor_entity_id)

        try:
            sun_elevation = float(sun_state.attributes.get(const.HA_SUN_ATTR_ELEVATION, 0))
            sun_azimuth = float(sun_state.attributes.get(const.HA_SUN_ATTR_AZIMUTH, 0))
        except (ValueError, TypeError) as err:
            raise InvalidSensorReadingError(sun_state.entity_id, str(sun_state.state)) from err

        # Store sensor attributes
        result.update(
            {
                const.SENSOR_ATTR_SUN_AZIMUTH: sun_azimuth,
                const.SENSOR_ATTR_SUN_ELEVATION: sun_elevation,
                const.SENSOR_ATTR_TEMP_CURRENT: temp_current,
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
            if state is None:
                const.LOGGER.warning(f"[{entity_id}] Cover unavailable, skipping")
                continue

            # Get cover features (e.g., SET_POSITION), defaulting to 0
            features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

            # Get the current position, defaulting to fully open
            current_pos = state.attributes.get(ATTR_CURRENT_POSITION)
            if current_pos is None:
                const.LOGGER.warning(f"[{entity_id}] Cover has no current_position attribute, assuming fully open")
                current_pos = const.COVER_POS_FULLY_OPEN

            # Outputs to determine
            sun_hitting: bool = False
            attrs: dict[str, Any] = {}

            # Cover azimuth
            cover_azimuth_raw = config.get(f"{entity_id}_{const.COVER_SFX_AZIMUTH}")
            cover_azimuth: float | None = to_float_or_none(cover_azimuth_raw)
            if cover_azimuth is None:
                error = f"[{entity_id}] Cover has invalid or missing azimuth (direction), skipping"
                const.LOGGER.warning(error)
                attrs[const.COVER_ATTR_ERROR] = error
                continue

            # Is the sun hitting the window?
            sun_azimuth_difference = self._calculate_angle_difference(sun_azimuth, cover_azimuth)
            if sun_elevation >= sun_elevation_threshold:
                sun_hitting = sun_azimuth_difference < resolved.sun_azimuth_tolerance
            else:
                sun_hitting = False

            # Calculate the cover position
            if temp_hot and weather_sunny and sun_hitting:
                # Close the cover (but respect max closure limit)
                desired_pos = max(const.COVER_POS_FULLY_CLOSED, resolved.covers_max_closure)
            else:
                # Open the cover
                desired_pos = const.COVER_POS_FULLY_OPEN

            # Determine if cover movement is necessary
            movement_needed = False
            if desired_pos == current_pos:
                message = "No movement needed"
            elif abs(desired_pos - current_pos) < covers_min_position_delta:
                message = "Skipping minor adjustment"
            else:
                message = "Moving cover"
                movement_needed = True

            # Store and log per-cover attributes
            cover_attrs = {
                const.COVER_ATTR_COVER_AZIMUTH: cover_azimuth,
                const.COVER_ATTR_POSITION_DESIRED: desired_pos,
                const.COVER_ATTR_SUN_AZIMUTH_DIFF: sun_azimuth_difference,
                const.COVER_ATTR_SUN_HITTING: sun_hitting,
            }
            attrs.update(cover_attrs)
            result[ConfKeys.COVERS.value][entity_id] = attrs

            # Log the attributes including current position
            cover_attrs[ATTR_CURRENT_POSITION] = current_pos
            cover_attrs[ATTR_SUPPORTED_FEATURES] = features
            const.LOGGER.debug(f"[{entity_id}] {message} {str(cover_attrs)}")

            if movement_needed:
                try:
                    await self._set_cover_position(entity_id, desired_pos, features)
                except ServiceCallError as err:
                    # Log the error but continue with other covers
                    const.LOGGER.error(f"[{entity_id}] Failed to control cover: {err}")
                    attrs[const.COVER_ATTR_ERROR] = str(err)
                except (ValueError, TypeError) as err:
                    # Parameter validation errors
                    error_msg = f"Invalid parameters for cover control: {err}"
                    const.LOGGER.error(f"[{entity_id}] {error_msg}")
                    attrs[const.COVER_ATTR_ERROR] = error_msg

        const.LOGGER.debug("Finished cover evaluation")

        return result

    #
    # _set_cover_position
    #
    async def _set_cover_position(self, entity_id: str, desired_pos: int, features: int) -> None:
        """Set cover position using the most appropriate service call.

        Args:
            entity_id: The cover entity ID to control
            desired_pos: Target position (0-100, where 0=closed, 100=open)
            features: Cover's supported features bitmask

        Raises:
            ServiceCallError: If the service call fails
            ValueError: If desired_pos is outside valid range (0-100)
        """

        # Validate position parameter
        if not (const.COVER_POS_FULLY_CLOSED <= desired_pos <= const.COVER_POS_FULLY_OPEN):
            raise ValueError(
                f"desired_pos must be between {const.COVER_POS_FULLY_CLOSED} and {const.COVER_POS_FULLY_OPEN}, got {desired_pos}"
            )

        try:
            if features & CoverEntityFeature.SET_POSITION:
                # The cover supports setting a specific position
                service = SERVICE_SET_COVER_POSITION
                service_data = {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: desired_pos}
                const.LOGGER.debug(f"[{entity_id}] Using set_position service to move to {desired_pos}%")
            else:
                # Fallback to open/close
                if desired_pos == const.COVER_POS_FULLY_OPEN:
                    service = SERVICE_OPEN_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    const.LOGGER.debug(f"[{entity_id}] Using open_cover service (no position support)")
                else:
                    service = SERVICE_CLOSE_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    const.LOGGER.debug(f"[{entity_id}] Using close_cover service (no position support)")

            resolved = self._resolved_settings()
            if resolved.simulating:
                # If simulation mode is enabled, skip the actual service call
                const.LOGGER.info(
                    f"[{entity_id}] Simulation mode enabled; skipping actual {service} call; would have moved to {desired_pos}%"
                )
            else:
                # Call the service
                await self.hass.services.async_call(Platform.COVER, service, service_data)

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
