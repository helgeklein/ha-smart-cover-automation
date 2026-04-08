"""Home Assistant API interface layer.

This module provides a clean abstraction layer over Home Assistant's APIs,
encapsulating all direct interactions with the HA core system.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import ATTR_POSITION, ATTR_TILT_POSITION, CoverEntityFeature
from homeassistant.components.logbook import async_log_entry
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.components.weather.const import ATTR_WEATHER_TEMPERATURE_UNIT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SUN_EVENT_SUNRISE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as ha_entity_registry
from homeassistant.helpers import translation
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from . import const
from .log import Log

MIN_TEMPERATURE_CUTOVER_OFFSET = timedelta(minutes=30)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from .config import ResolvedConfig


#
# Exception classes
#
class SmartCoverHAError(Exception):
    """Base class for HA interface errors."""


class WeatherEntityNotFoundError(SmartCoverHAError):
    """Weather entity could not be found."""

    def __init__(self, sensor_name: str) -> None:
        super().__init__(f"Weather entity '{sensor_name}' not found")
        self.sensor_name = sensor_name


class InvalidSensorReadingError(SmartCoverHAError):
    """Invalid sensor reading received."""

    def __init__(self, sensor_name: str, value: str) -> None:
        super().__init__(f"Invalid reading from '{sensor_name}': {value}")
        self.sensor_name = sensor_name
        self.value = value


class ServiceCallError(SmartCoverHAError):
    """Service call failed."""

    def __init__(self, service: str, entity_id: str, error: str) -> None:
        super().__init__(f"Failed to call {service} for {entity_id}: {error}")
        self.service = service
        self.entity_id = entity_id
        self.error = error


#
# HomeAssistantInterface
#
class HomeAssistantInterface:
    """Encapsulates all Home Assistant API interactions.

    This class provides a clean interface to Home Assistant's core APIs,
    keeping the automation logic decoupled from HA implementation details.
    """

    #
    # __init__
    #
    def __init__(
        self,
        hass: HomeAssistant,
        resolved_settings_callback: Callable[[], ResolvedConfig],
        logger: Log,
    ) -> None:
        """Initialize the HA interface.

        Args:
            hass: Home Assistant instance
            resolved_settings_callback: Callback to get current resolved configuration
            logger: Instance-specific logger with entry_id prefix
        """

        self.hass = hass
        self._resolved_settings_callback = resolved_settings_callback
        self._logger = logger
        self.status_sensor_unique_id: str | None = None

    #
    # set_cover_position
    #
    async def set_cover_position(self, entity_id: str, desired_pos: int, features: int) -> int:
        """Set cover position using the most appropriate service call.

        Args:
            entity_id: The cover entity ID to control
            desired_pos: Target position (0-100, where 0=closed, 100=open)
            features: Cover's supported features bitmask

        Returns:
            The actual position to which the cover was moved (0-100)

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
                self._logger.debug(f"[{entity_id}] Moving to {desired_pos}% via set_position service")
            else:
                # Fallback to open/close - determine actual position based on service used
                if desired_pos > const.COVER_POS_FULLY_OPEN / 2:
                    service = SERVICE_OPEN_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_position = const.COVER_POS_FULLY_OPEN  # Binary covers go to fully open
                    self._logger.debug(f"[{entity_id}] Opening fully via open_cover service (no position support)")
                else:
                    service = SERVICE_CLOSE_COVER
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_position = const.COVER_POS_FULLY_CLOSED  # Binary covers go to fully closed
                    self._logger.debug(f"[{entity_id}] Closing fully via close_cover service (no position support)")

            resolved = self._resolved_settings_callback()
            if resolved.simulation_mode:
                # If simulation mode is enabled, skip the actual service call
                self._logger.info(
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
            self._logger.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

        except (ValueError, TypeError) as err:
            # Invalid parameters or data type issues
            error_msg = f"Invalid parameters for cover control: {err}"
            self._logger.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

        except Exception as err:
            # Catch-all for unexpected errors
            error_msg = f"Unexpected error during cover control: {err}"
            self._logger.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

    #
    # set_cover_tilt_position
    #
    async def set_cover_tilt_position(self, entity_id: str, tilt_position: int, features: int) -> int:
        """Set cover tilt position using the most appropriate service call.

        Args:
            entity_id: The cover entity ID to control
            tilt_position: Target tilt (0=closed/vertical, 100=open/horizontal)
            features: Cover's supported features bitmask

        Returns:
            The actual tilt position set

        Raises:
            ServiceCallError: If the service call fails
            ValueError: If tilt_position is outside valid range (0-100)
        """

        # Validate tilt position parameter
        if not (const.COVER_POS_FULLY_CLOSED <= tilt_position <= const.COVER_POS_FULLY_OPEN):
            raise ValueError(
                f"tilt_position must be between {const.COVER_POS_FULLY_CLOSED} and {const.COVER_POS_FULLY_OPEN}, got {tilt_position}"
            )

        # Initialize service name and actual tilt for error handling and return value
        service = "unknown_service"
        actual_tilt = None

        try:
            if int(features) & CoverEntityFeature.SET_TILT_POSITION:
                # The cover supports setting a specific tilt position
                service = SERVICE_SET_COVER_TILT_POSITION
                service_data = {ATTR_ENTITY_ID: entity_id, ATTR_TILT_POSITION: tilt_position}
                actual_tilt = tilt_position
                self._logger.debug(f"[{entity_id}] Setting tilt to {tilt_position}% via set_cover_tilt_position service")
            else:
                # Fallback to open_tilt/close_tilt
                if tilt_position > const.COVER_POS_FULLY_OPEN / 2:
                    service = SERVICE_OPEN_COVER_TILT
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_tilt = const.COVER_POS_FULLY_OPEN  # Binary tilt goes fully open
                    self._logger.debug(f"[{entity_id}] Opening tilt fully via open_cover_tilt service (no tilt position support)")
                else:
                    service = SERVICE_CLOSE_COVER_TILT
                    service_data = {ATTR_ENTITY_ID: entity_id}
                    actual_tilt = const.COVER_POS_FULLY_CLOSED  # Binary tilt goes fully closed
                    self._logger.debug(f"[{entity_id}] Closing tilt fully via close_cover_tilt service (no tilt position support)")

            resolved = self._resolved_settings_callback()
            if resolved.simulation_mode:
                self._logger.info(
                    f"[{entity_id}] Simulation mode enabled; skipping actual {service} call; would have set tilt to {actual_tilt}%"
                )
            else:
                await self.hass.services.async_call(Platform.COVER, service, service_data)

            return actual_tilt

        except (OSError, ConnectionError, TimeoutError) as err:
            error_msg = f"Communication error while controlling cover tilt: {err}"
            self._logger.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

        except (ValueError, TypeError) as err:
            error_msg = f"Invalid parameters for cover tilt control: {err}"
            self._logger.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

        except Exception as err:
            error_msg = f"Unexpected error during cover tilt control: {err}"
            self._logger.error(f"[{entity_id}] {error_msg}")
            raise ServiceCallError(service, entity_id, str(err)) from err

    #
    # get_weather_condition
    #
    def get_weather_condition(self, entity_id: str) -> str:
        """Get the current weather condition from a weather entity.

        Args:
            entity_id: Entity ID of the weather entity

        Returns:
            The current weather condition as a string

        Raises:
            WeatherEntityNotFoundError: If the weather entity doesn't exist
            InvalidSensorReadingError: If the state is unavailable or invalid
        """

        state = self.hass.states.get(entity_id)
        if state is None:
            raise WeatherEntityNotFoundError(entity_id)

        if state.state in (None, "unavailable", "unknown"):
            raise InvalidSensorReadingError(entity_id, f"Weather entity {entity_id}: state is unavailable")

        condition = state.state
        return condition

    #
    # get_sun_data
    #
    def get_sun_data(self) -> tuple[float, float]:
        """Get required data from the sun entity.

        Returns:
            Tuple of (azimuth, elevation) in degrees

        Raises:
            Exception: If sun entity not found or data unavailable (raised by coordinator)
        """
        from .util import to_float_or_none

        # Get sun entity
        sun_entity = self.hass.states.get(const.HA_SUN_ENTITY_ID)
        if sun_entity is None:
            from .coordinator import SunSensorNotFoundError

            raise SunSensorNotFoundError(const.HA_SUN_ENTITY_ID)

        # Get sun elevation
        sun_elevation = to_float_or_none(sun_entity.attributes.get(const.HA_SUN_ATTR_ELEVATION))
        if sun_elevation is None:
            raise InvalidSensorReadingError(const.HA_SUN_ENTITY_ID, "Sun elevation unavailable")

        # Get sun azimuth
        sun_azimuth = to_float_or_none(sun_entity.attributes.get(const.HA_SUN_ATTR_AZIMUTH, 0))
        if sun_azimuth is None:
            raise InvalidSensorReadingError(const.HA_SUN_ENTITY_ID, "Sun azimuth unavailable")

        return (sun_azimuth, sun_elevation)

    #
    # get_sun_state
    #
    def get_sun_state(self) -> str | None:
        """Get the sun entity's state (above_horizon or below_horizon).

        Returns:
            The sun state as a string, or None if sun entity is not available

        Note:
            Unlike get_sun_data(), this method returns None instead of raising an exception
            when the sun entity is unavailable, since the state check is optional.
        """
        sun_entity = self.hass.states.get(const.HA_SUN_ENTITY_ID)
        if sun_entity is None:
            return None

        return sun_entity.state

    #
    # get_entity_state
    #
    def get_entity_state(self, entity_id: str) -> str | None:
        """Get the state of any entity.

        Args:
            entity_id: The entity ID to get the state for

        Returns:
            The entity state as a string, or None if entity is not available
        """
        entity = self.hass.states.get(entity_id)
        if entity is None:
            return None

        return entity.state

    #
    # get_daily_temperature_extrema
    #
    async def get_daily_temperature_extrema(self, entity_id: str) -> tuple[float, float | None]:
        """Get today's forecasted maximum and minimum temperatures.

        Args:
            entity_id: Entity ID of the weather entity

        Returns:
            Tuple of (daily_max_temperature, daily_min_temperature) in degrees Celsius.
            The daily minimum temperature is None when the forecast low is unavailable.

        Raises:
            WeatherEntityNotFoundError: If the weather entity doesn't exist
            InvalidSensorReadingError: If the forecast maximum temperature is unavailable
        """

        state = self.hass.states.get(entity_id)
        if state is None:
            raise WeatherEntityNotFoundError(entity_id)

        forecast_list = await self._get_forecast_list(entity_id)
        if forecast_list is None:
            raise InvalidSensorReadingError(entity_id, "Forecast temperature unavailable")

        max_forecast_result = self._find_day_forecast(forecast_list, "max")
        if max_forecast_result is None:
            raise InvalidSensorReadingError(entity_id, "Forecast temperature unavailable")

        applicable_day, max_day_forecast = max_forecast_result
        max_temp = self._extract_max_temperature(max_day_forecast)
        if max_temp is None:
            self._logger.warning(
                "Could not extract forecast maximum temperature from %s for %s. max=%s",
                entity_id,
                applicable_day,
                max_temp,
            )
            raise InvalidSensorReadingError(entity_id, "Forecast temperature unavailable")

        min_forecast_result = self._find_day_forecast(forecast_list, "min")
        min_temp = None
        if min_forecast_result is not None:
            min_applicable_day, min_day_forecast = min_forecast_result
            min_temp = self._extract_min_temperature(min_day_forecast)
        else:
            min_applicable_day = "unknown"

        if min_temp is None:
            self._logger.warning(
                "Could not extract forecast minimum temperature from %s for %s. Continuing with daily max only.",
                entity_id,
                min_applicable_day,
            )

        return (
            self._convert_forecast_temperature_to_celsius(state, max_temp),
            self._convert_forecast_temperature_to_celsius(state, min_temp) if min_temp is not None else None,
        )

    #
    # get_max_temperature
    #
    async def get_max_temperature(self, entity_id: str) -> float:
        """Get today's maximum temperature value from a weather forecast.

        Args:
            entity_id: Entity ID of the weather entity

        Returns:
            The forecasted maximum temperature in degrees Celsius

        Raises:
            WeatherEntityNotFoundError: If the weather entity doesn't exist
            InvalidSensorReadingError: If the forecast is unavailable
        """

        state = self.hass.states.get(entity_id)
        if state is None:
            raise WeatherEntityNotFoundError(entity_id)

        forecast_temp = await self._get_forecast_max_temp(entity_id)
        if forecast_temp is not None:
            return self._convert_forecast_temperature_to_celsius(state, forecast_temp)

        # If forecast is not available, raise an error
        raise InvalidSensorReadingError(entity_id, "Forecast temperature unavailable")

    #
    # get_min_temperature
    #
    async def get_min_temperature(self, entity_id: str) -> float:
        """Get today's minimum temperature value from a weather forecast.

        Args:
            entity_id: Entity ID of the weather entity

        Returns:
            The forecasted minimum temperature in degrees Celsius

        Raises:
            WeatherEntityNotFoundError: If the weather entity doesn't exist
            InvalidSensorReadingError: If the forecast is unavailable
        """

        state = self.hass.states.get(entity_id)
        if state is None:
            raise WeatherEntityNotFoundError(entity_id)

        forecast_temp = await self._get_forecast_min_temp(entity_id)
        if forecast_temp is not None:
            return self._convert_forecast_temperature_to_celsius(state, forecast_temp)

        raise InvalidSensorReadingError(entity_id, "Forecast temperature unavailable")

    #
    # _convert_forecast_temperature_to_celsius
    #
    def _convert_forecast_temperature_to_celsius(self, state: Any, forecast_temp: float) -> float:
        """Convert a forecast temperature to Celsius when required."""

        unit = state.attributes.get(ATTR_WEATHER_TEMPERATURE_UNIT)
        if unit == UnitOfTemperature.FAHRENHEIT:
            celsius_temp = (forecast_temp - 32) * 5.0 / 9.0
            self._logger.debug(f"Converted forecast temperature from {forecast_temp}° Fahrenheit to {celsius_temp}° Celsius")
            return celsius_temp

        return forecast_temp

    #
    # _get_day_forecast
    #
    async def _get_forecast_list(self, entity_id: str) -> list[Any] | None:
        """Return the validated daily forecast list for a weather entity."""

        try:
            service_data = {"entity_id": entity_id, "type": "daily"}
            response = await self.hass.services.async_call(
                Platform.WEATHER, SERVICE_GET_FORECASTS, service_data, blocking=True, return_response=True
            )

            self._logger.debug(f"Weather forecast service response for {entity_id}: {response}")

            if not (response and isinstance(response, dict) and entity_id in response):
                self._logger.warning(f"Invalid or empty forecast response for {entity_id}: {response}")
                return None

            entity_data = response[entity_id]
            if not (isinstance(entity_data, dict) and "forecast" in entity_data):
                self._logger.warning(
                    f"Forecast data missing in response for {entity_id}. Available keys: {list(entity_data.keys()) if isinstance(entity_data, dict) else 'Not a dict'}"
                )
                return None

            forecast_list = entity_data["forecast"]
            if not (isinstance(forecast_list, list) and forecast_list):
                self._logger.warning(
                    f"Forecast list is empty or not a list for {entity_id}: {type(forecast_list)} with length {len(forecast_list) if isinstance(forecast_list, list) else 'N/A'}"
                )
                return None

            return forecast_list

        except HomeAssistantError as err:
            self._logger.warning(f"Failed to call weather forecast service for {entity_id}: {err}")
        except Exception as err:
            self._logger.warning(f"Unexpected error getting weather forecast from {entity_id}: {err}")

        return None

    #
    # _get_day_forecast
    #
    async def _get_day_forecast(self, entity_id: str, temperature_kind: str = "max") -> tuple[str, dict[str, Any]] | None:
        """Return the applicable daily forecast entry for today or tomorrow."""

        forecast_list = await self._get_forecast_list(entity_id)
        if forecast_list is None:
            return None

        return self._find_day_forecast(forecast_list, temperature_kind)

    #
    # _get_forecast_max_temp
    #
    async def _get_forecast_max_temp(self, entity_id: str) -> float | None:
        """Get the max temperature from today's weather forecast."""

        forecast_result = await self._get_day_forecast(entity_id, "max")
        if forecast_result is None:
            return None

        applicable_day, day_forecast = forecast_result
        max_temp = self._extract_max_temperature(day_forecast)
        if max_temp is not None:
            self._logger.debug(f"Forecast max temperature: {max_temp} °C for {applicable_day}")
            return max_temp

        self._logger.warning(f"Could not extract max temperature from today's forecast for {entity_id}")

        return None

    #
    # _get_forecast_min_temp
    #
    async def _get_forecast_min_temp(self, entity_id: str) -> float | None:
        """Get the min temperature from today's weather forecast."""

        forecast_result = await self._get_day_forecast(entity_id, "min")
        if forecast_result is None:
            return None

        applicable_day, day_forecast = forecast_result
        min_temp = self._extract_min_temperature(day_forecast)
        if min_temp is not None:
            self._logger.debug(f"Forecast min temperature: {min_temp} °C for {applicable_day}")
            return min_temp

        self._logger.warning(f"Could not extract min temperature from today's forecast for {entity_id}")

        return None

    #
    # _find_day_forecast
    #
    def _find_day_forecast(self, forecast_list: list[Any], temperature_kind: str = "max") -> tuple[str, dict[str, Any]] | None:
        """Find the applicable daily forecast from the forecast list.

        Args:
            forecast_list: List of forecast dictionaries

        Returns:
            Tuple of (day_name, forecast_dict) or None if not found
        """

        if not forecast_list:
            self._logger.warning("Forecast list is empty")
            return None

        now_local = dt_util.now()
        applicable_day, applicable_day_friendly = self._get_applicable_forecast_day(now_local, temperature_kind)

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
                self._logger.debug(f"Could not parse forecast datetime '{datetime_field}': {err}")
                continue

        # Fallback: could not find forecast by date
        self._logger.warning("Could not find weather forecast by date")
        return None

    #
    # _get_applicable_forecast_day
    #
    def _get_applicable_forecast_day(self, now_local: datetime, temperature_kind: str) -> tuple[date, str]:
        """Return the applicable forecast day for maximum or minimum temperatures."""

        resolved = self._resolved_settings_callback()

        if temperature_kind == "min":
            min_cutover = self._get_min_temperature_cutover_datetime(now_local.date())
            if min_cutover is not None:
                if now_local >= min_cutover:
                    return ((now_local + timedelta(days=1)).date(), "tomorrow")
                return (now_local.date(), "today")

            self._logger.debug(
                "Could not determine sunrise-based min temperature cutover for %s; falling back to max temperature cutover time",
                now_local.date().isoformat(),
            )

        if now_local.time() >= resolved.weather_hot_cutover_time:
            return ((now_local + timedelta(days=1)).date(), "tomorrow")

        return (now_local.date(), "today")

    #
    # _get_min_temperature_cutover_datetime
    #
    def _get_min_temperature_cutover_datetime(self, target_date: date) -> datetime | None:
        """Return the min-temperature cutover datetime, 30 minutes before sunrise."""

        try:
            sunrise_time = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE, target_date)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            self._logger.debug(
                "Could not determine sunrise time for %s while resolving min temperature cutover: %s",
                target_date.isoformat(),
                err,
            )
            return None

        if sunrise_time is None:
            return None

        if not isinstance(sunrise_time, datetime):
            self._logger.debug(
                "Could not determine sunrise time for %s while resolving min temperature cutover: unexpected type %s",
                target_date.isoformat(),
                type(sunrise_time).__name__,
            )
            return None

        return dt_util.as_local(sunrise_time - MIN_TEMPERATURE_CUTOVER_OFFSET)

    #
    # _extract_max_temperature
    #
    def _extract_max_temperature(self, forecast: dict[str, Any]) -> float | None:
        """Extract maximum temperature from forecast entry.

        Args:
            forecast: Forecast dictionary

        Returns:
            Maximum temperature value or None if not found
        """

        # Temperature field names in order of preference
        temp_fields = [
            "native_temperature",  # Official HA field
            "temperature",  # Most common
            "temp_max",
            "temp_high",
            "temphigh",
            "high",
            "max_temp",
        ]

        return self._extract_temperature(forecast, temp_fields)

    #
    # _extract_min_temperature
    #
    def _extract_min_temperature(self, forecast: dict[str, Any]) -> float | None:
        """Extract minimum temperature from forecast entry."""

        temp_fields = [
            "native_templow",
            "templow",
            "temp_low",
            "temp_min",
            "low",
            "min_temp",
            "minimum_temperature",
        ]

        return self._extract_temperature(forecast, temp_fields)

    #
    # _extract_temperature
    #
    def _extract_temperature(self, forecast: dict[str, Any], temp_fields: list[str]) -> float | None:
        """Extract a temperature value from a forecast entry using a priority list."""

        if not isinstance(forecast, dict):
            return None

        for field_name in temp_fields:
            if field_name in forecast:
                temp_value = forecast[field_name]
                if isinstance(temp_value, (int, float)):
                    return float(temp_value)
                else:
                    self._logger.debug(f"Field '{field_name}' is not a number: {temp_value}")

        self._logger.warning(f"No temperature fields found in forecast. Available fields: {list(forecast.keys())}")
        return None

    #
    # add_logbook_entry
    #
    async def add_logbook_entry(
        self,
        verb_key: str,
        entity_id: str,
        reason_key: str,
        target_pos: int,
    ) -> None:
        """Add a detailed logbook entry for cover movement.

        Args:
            verb_key: Translation key for the verb (e.g., "opening", "closing")
            entity_id: Cover entity ID
            reason_key: Translation key for the reason
            target_pos: Target position percentage
        """

        try:
            # Look up the entity ID from the entity registry using the stored unique_id
            registry = ha_entity_registry.async_get(self.hass)
            unique_id = self.status_sensor_unique_id

            # Find the entity by unique_id
            integration_entity_id = None
            for entity in registry.entities.values():
                if entity.unique_id == unique_id and entity.platform == const.DOMAIN:
                    integration_entity_id = entity.entity_id
                    break

            if integration_entity_id is None:
                self._logger.warning(f"Could not find integration entity for logbook entry by its unique_id: {unique_id}")
                return

            # Get translations for the current language
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
                self._logger.warning(
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
            self._logger.debug(f"[{entity_id}] Failed to add logbook entry: {err}")
