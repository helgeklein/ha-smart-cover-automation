"""Implementation of the automation logic."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature
from homeassistant.components.logbook import async_log_entry
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    Platform,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as ha_entity_registry
from homeassistant.helpers import translation
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator as BaseCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import const
from .automation_engine import AutomationEngine
from .config import ConfKeys, ResolvedConfig, resolve_entry
from .cover_position_history import CoverPositionHistoryManager
from .data import CoordinatorData

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
            engine = AutomationEngine(
                hass=self.hass,
                resolved=resolved,
                config=config,
                cover_pos_history_mgr=self._cover_pos_history_mgr,
                get_max_temperature_callback=self._get_max_temperature,
                get_weather_condition_callback=self._get_weather_condition,
                log_automation_result_callback=self._log_automation_result,
                log_cover_result_callback=self._log_cover_result,
                nighttime_check_callback=self._nighttime_and_block_opening,
                time_period_check_callback=self._in_time_period_automation_disabled,
                set_cover_position_callback=self._set_cover_position,
                add_logbook_entry_callback=self._add_logbook_entry_cover_movement,
            )

            return await engine.run(states)

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
    ) -> None:
        """Log and store the the result for one cover."""
        message = f"[{entity_id}] {error_description}"
        const.LOGGER.info(message)

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
