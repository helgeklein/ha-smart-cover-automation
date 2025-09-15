"""Implementation of the automation logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_POSITION, CoverEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    Platform,
)
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


class TempSensorNotFoundError(SmartCoverError):
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


class AllCoversUnavailableError(SmartCoverError):
    """All covers are unavailable."""

    def __init__(self) -> None:
        super().__init__("All covers are unavailable")


class ConfigurationError(SmartCoverError):
    """Configuration is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Configuration error: {message}")
        self.message = message


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
        """
        try:
            const.LOGGER.info("Starting cover automation update")

            # Keep a reference to raw config for dynamic per-cover direction
            config = self.config_entry.runtime_data.config

            # Get the resolved settings
            resolved = self._resolved_settings()

            # Get the configured covers
            covers = tuple(resolved.covers)
            if not covers:
                raise ConfigurationError("No covers configured")

            # Get the enabled state
            enabled = resolved.enabled
            if not enabled:
                const.LOGGER.info("Automation disabled via configuration; skipping actions")
                return {ConfKeys.COVERS.value: {}}

            # Collect states for all configured covers
            states: dict[str, State | None] = {entity_id: self.hass.states.get(entity_id) for entity_id in covers}
            available_covers = sum(1 for s in states.values() if s is not None)
            if available_covers == 0:
                raise AllCoversUnavailableError()

            return await self._handle_automation(states, config)

        except SmartCoverError:
            raise
        except (KeyError, AttributeError) as err:
            raise ConfigurationError(str(err)) from err
        except (OSError, ValueError, TypeError) as err:
            raise UpdateFailed(f"System error during automation update: {err}") from err
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

        # Temperature input
        temp_threshold = resolved.temp_threshold
        sensor_entity_id = resolved.temp_sensor_entity_id
        temp_hysteresis = resolved.temp_hysteresis
        temp_state = self.hass.states.get(sensor_entity_id)
        if temp_state is None:
            raise TempSensorNotFoundError(sensor_entity_id)
        try:
            temp_current = float(temp_state.state)
        except (ValueError, TypeError) as err:
            raise InvalidSensorReadingError(temp_state.entity_id, str(temp_state.state)) from err

        # Temperature above threshold?
        temp_hot = False
        if temp_current > temp_threshold + temp_hysteresis:
            temp_hot = True

        # Cover settings
        covers_min_position_delta = resolved.covers_min_position_delta

        # Sun input
        sun_elevation: float | None = None
        sun_azimuth: float | None = None
        sun_elevation_threshold = resolved.sun_elevation_threshold
        sensor_entity_id = const.HA_SUN_ENTITY_ID
        sun_state = self.hass.states.get(sensor_entity_id)
        if sun_state is None:
            # Required sun entity missing
            raise SunSensorNotFoundError(sensor_entity_id)

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
            if temp_hot and sun_hitting:
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
    # _calculate_angle_difference
    #
    def _calculate_angle_difference(self, sun_azimuth: float, cover_azimuth: float) -> float:
        """Calculate minimal absolute angle difference between two azimuths."""
        return abs(((sun_azimuth - cover_azimuth + 180) % 360) - 180)
