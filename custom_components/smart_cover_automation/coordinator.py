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
from .config import CONF_SPECS, ConfKeys, ResolvedConfig, resolve_entry
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
            if bool(resolved.verbose_logging):
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
            enabled = bool(resolved.enabled)
            if not enabled:
                const.LOGGER.info("Automation disabled via configuration; skipping actions")
                return {ConfKeys.COVERS.value: {}}

            # Collect states for all configured covers
            states: dict[str, State | None] = {entity_id: self.hass.states.get(entity_id) for entity_id in covers}
            available_covers = sum(1 for s in states.values() if s is not None)
            if available_covers == 0:
                raise AllCoversUnavailableError()
            for entity_id, state in states.items():
                if state is None:
                    const.LOGGER.warning(f"Cover {entity_id} is unavailable")

            return await self._handle_automation(states, config)

        except SmartCoverError:
            raise
        except (KeyError, AttributeError) as err:
            raise ConfigurationError(str(err)) from err
        except (OSError, ValueError, TypeError) as err:
            raise UpdateFailed(f"System error during automation update: {err}") from err

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
        temp_available = False
        current_temp: float | None = None
        max_temp = float(resolved.max_temperature)
        min_temp = float(resolved.min_temperature)
        sensor_entity_id = resolved.temp_sensor_entity_id
        temp_state = self.hass.states.get(sensor_entity_id)
        if temp_state is None:
            # Required temp sensor missing
            raise TempSensorNotFoundError(sensor_entity_id)
        try:
            current_temp = float(temp_state.state)
            temp_available = True
        except (ValueError, TypeError) as err:
            raise InvalidSensorReadingError(temp_state.entity_id, str(temp_state.state)) from err

        temp_hysteresis = float(resolved.temperature_hysteresis)
        min_position_delta = int(float(resolved.min_position_delta))

        # Sun input
        sun_available = False
        elevation: float | None = None
        azimuth: float | None = None
        threshold = float(resolved.sun_elevation_threshold)
        sensor_entity_id = const.SUN_ENTITY_ID
        sun_state = self.hass.states.get(sensor_entity_id)
        if sun_state is None:
            # Required sun entity missing
            raise SunSensorNotFoundError(sensor_entity_id)
        try:
            elevation = float(sun_state.attributes.get(const.SUN_ATTR_ELEVATION, 0))
            azimuth = float(sun_state.attributes.get(const.SUN_ATTR_AZIMUTH, 0))
            sun_available = True
        except (ValueError, TypeError) as err:
            raise InvalidSensorReadingError(sun_state.entity_id, str(sun_state.state)) from err

        # Iterate covers
        for entity_id, state in states.items():
            if not state:
                const.LOGGER.warning(f"Skipping unavailable cover: {entity_id}")
                continue

            features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            current_pos = state.attributes.get(ATTR_CURRENT_POSITION)

            desired_from_temp: int | None = None
            desired_from_sun: int | None = None
            temp_hot: bool = False
            sun_hitting: bool = False
            details: dict[str, Any] = {}

            # Temperature contribution
            if temp_available and current_temp is not None:
                if current_temp > max_temp + temp_hysteresis:
                    desired_from_temp = const.COVER_POS_FULLY_CLOSED
                    temp_hot = True
                elif current_temp < min_temp - temp_hysteresis:
                    desired_from_temp = const.COVER_POS_FULLY_OPEN
                else:
                    desired_from_temp = current_pos
                details.update(
                    {
                        const.ATTR_TEMP_CURRENT: current_temp,
                        const.ATTR_TEMP_MAX_THRESH: max_temp,
                        const.ATTR_TEMP_MIN_THRESH: min_temp,
                        const.ATTR_TEMP_HYSTERESIS: temp_hysteresis,
                        "desired_from_temp": desired_from_temp,
                        "temp_hot": temp_hot,
                    }
                )
                const.LOGGER.debug(
                    "Temp eval %s: current=%.2f, range=[%.2f, %.2f], hysteresis=%.2f => desired_from_temp=%s, temp_hot=%s",
                    entity_id,
                    current_temp,
                    min_temp,
                    max_temp,
                    temp_hysteresis,
                    desired_from_temp,
                    temp_hot,
                )
            else:
                details["temp_unavailable"] = True

            # Sun contribution
            if sun_available and elevation is not None and azimuth is not None:
                # Per-cover direction remains dynamic and stored in config by entity_id
                direction_raw = config.get(f"{entity_id}_{const.COVER_AZIMUTH}")
                direction_azimuth: float | None = to_float_or_none(direction_raw)

                if direction_azimuth is not None:
                    tolerance = int(float(resolved.azimuth_tolerance))
                    # Compute sun desired position and whether the sun is hitting the window
                    angle_difference = None
                    if elevation >= threshold:
                        angle_difference = self._calculate_angle_difference(azimuth, direction_azimuth)
                        sun_hitting = angle_difference < tolerance
                    else:
                        sun_hitting = False

                    desired_from_sun = self._calculate_desired_position(elevation, azimuth, threshold, direction_azimuth, entity_id)
                    details.update(
                        {
                            const.ATTR_SUN_ELEVATION: elevation,
                            const.ATTR_SUN_AZIMUTH: azimuth,
                            const.ATTR_SUN_ELEVATION_THRESH: threshold,
                            "window_direction_azimuth": direction_azimuth,
                            "angle_difference": angle_difference,
                            "desired_from_sun": desired_from_sun,
                            "sun_hitting": sun_hitting,
                        }
                    )
                    const.LOGGER.debug(
                        f"Sun eval {entity_id}: elev={elevation:.2f}(threshold={threshold:.2f}) azimuth={azimuth:.2f} window={direction_azimuth:.2f} angle_diff={angle_difference} hit={sun_hitting} => desired_from_sun={desired_from_sun}"
                    )
                else:
                    const.LOGGER.warning(f"Cover {entity_id}: invalid or missing direction for sun logic")
                    details["sun_direction_invalid"] = True
            else:
                details["sun_unavailable"] = True

            desired_pos = current_pos

            # Determine which automations are active
            include_temp = desired_from_temp is not None
            include_sun = desired_from_sun is not None and not details.get("sun_direction_invalid")

            if include_temp and not include_sun:
                # Temperature-only automation
                desired_pos = desired_from_temp
            elif include_sun and not include_temp:
                # Sun-only automation
                desired_pos = desired_from_sun
            elif include_temp and include_sun:
                # Combined automation: Close when both want to close, open when either wants to open
                if temp_hot and sun_hitting:
                    # Both conditions want to close
                    desired_pos = desired_from_sun  # Use sun's desired position (typically closed)
                elif (desired_from_temp == const.COVER_POS_FULLY_OPEN) or (desired_from_sun == const.COVER_POS_FULLY_OPEN):
                    # At least one condition wants to open
                    desired_pos = const.COVER_POS_FULLY_OPEN
                else:
                    # Neither condition is clearly wanting to close or open (comfortable temps, etc.)
                    desired_pos = current_pos  # Keep current position
            elif details.get("sun_direction_invalid") and include_temp:
                # Fallback: if sun direction invalid, behave as temperature-only
                desired_pos = desired_from_temp
            else:
                # No valid automation configured
                desired_pos = current_pos

            const.LOGGER.debug(
                f"Combine {entity_id}: temp_hot={temp_hot} sun_hitting={sun_hitting} desired_temp={desired_from_temp} desired_sun={desired_from_sun} => desired={desired_pos} (close_when_both_hot_and_hitting, open_when_either_wants_open)"
            )

            # Act with min delta
            if (
                desired_pos is not None
                and current_pos is not None
                and desired_pos != current_pos
                and abs(desired_pos - current_pos) < min_position_delta
            ):
                const.LOGGER.debug(
                    f"Skip small adjust {entity_id}: current={current_pos} desired={desired_pos} delta={abs(desired_pos - current_pos)} < min_delta={min_position_delta}"
                )
            elif desired_pos is not None and desired_pos != current_pos:
                const.LOGGER.info(f"[{entity_id}] Action: current={current_pos} desired={desired_pos} (features={features})")
                await self._set_cover_position(entity_id, desired_pos, features)

            details.update(
                {
                    "current_position": current_pos,
                    "desired_position": desired_pos,
                    const.ATTR_MIN_POSITION_DELTA: min_position_delta,
                    ConfKeys.MAX_CLOSURE.value: int(float(resolved.max_closure)),
                    "combined_strategy": "close_and_open_or",
                }
            )

            result[ConfKeys.COVERS.value][entity_id] = details

        return result

    #
    # _set_cover_position
    #
    async def _set_cover_position(self, entity_id: str, desired_pos: int, features: int) -> None:
        try:
            if features & CoverEntityFeature.SET_POSITION:
                const.LOGGER.info(f"[{entity_id}] Using set_cover_position to {desired_pos} (features={features})")
                await self.hass.services.async_call(
                    Platform.COVER,
                    SERVICE_SET_COVER_POSITION,
                    {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: desired_pos},
                )
            elif desired_pos == const.COVER_POS_FULLY_CLOSED:
                const.LOGGER.info(f"[{entity_id}] Closing cover")
                await self.hass.services.async_call(Platform.COVER, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id})
            elif desired_pos == const.COVER_POS_FULLY_OPEN:
                const.LOGGER.info(f"[{entity_id}] Opening cover")
                await self.hass.services.async_call(Platform.COVER, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id})
            else:
                const.LOGGER.warning(f"Cannot set cover {entity_id} position: desired={desired_pos}, features={features}")
        except (OSError, ValueError, TypeError, RuntimeError) as err:
            const.LOGGER.error(f"Failed to control cover {entity_id}: {err}")

    #
    # _calculate_desired_position
    #
    def _calculate_desired_position(
        self,
        elevation: float,
        azimuth: float,
        threshold: float,
        direction_azimuth: float,
        entity_id: str,
    ) -> int:
        """Calculate desired cover position for sun logic."""
        resolved = self._resolved_settings()
        try:
            max_closure = int(float(resolved.max_closure))
        except (TypeError, ValueError):
            max_closure = int(CONF_SPECS[ConfKeys.MAX_CLOSURE].default)

        if elevation < threshold:
            # Sun is low, open covers
            const.LOGGER.debug(
                f"Desired {entity_id} (sun low): elevation={elevation:.2f}<threshold={threshold:.2f} => {const.COVER_POS_FULLY_OPEN}"
            )
            return const.COVER_POS_FULLY_OPEN

        # Calculate angle between sun and window
        angle_diff = self._calculate_angle_difference(azimuth, direction_azimuth)
        tolerance = int(float(self._resolved_settings().azimuth_tolerance))
        if angle_diff < tolerance:
            desired_pos = max(const.COVER_POS_FULLY_CLOSED, const.COVER_POS_FULLY_OPEN - max_closure)
        else:
            desired_pos = const.COVER_POS_FULLY_OPEN
        const.LOGGER.debug(
            f"Desired {entity_id} (sun): angle_diff={angle_diff:.2f} tol={tolerance} max_closure={max_closure} => {desired_pos}"
        )
        return round(desired_pos)

    def _calculate_angle_difference(self, azimuth: float, direction_azimuth: float) -> float:
        """Calculate minimal absolute angle difference between two azimuths."""
        return abs(((azimuth - direction_azimuth + 180) % 360) - 180)
