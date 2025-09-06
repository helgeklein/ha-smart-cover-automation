"""
Smart cover automation coordinator.

Provides automation logic for controlling covers based on temperature and sun
position. Runs on a 60-second interval and exposes the last exception via
DataUpdateCoordinator.last_exception.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator as BaseCoordinator,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import const

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

    from .data import IntegrationConfigEntry

# Constants
COVER_FULLY_OPEN: Final = 100
COVER_FULLY_CLOSED: Final = 0
UPDATE_INTERVAL: Final = timedelta(seconds=60)

# Error messages
ERR_NO_TEMP_SENSOR = "Temperature sensor not found"
ERR_INVALID_TEMP = "Invalid temperature reading"
ERR_NO_SUN = "Sun integration not found"
ERR_INVALID_SUN = "Invalid sun position data"
ERR_SERVICE_CALL = "Service call failed"
ERR_ENTITY_UNAVAILABLE = "Entity is unavailable"
ERR_INVALID_CONFIG = "Invalid configuration"


class SmartCoverError(UpdateFailed):
    """Base class for smart cover automation errors."""


class SensorNotFoundError(SmartCoverError):
    """Temperature sensor could not be found."""

    def __init__(self, sensor_name: str = "sensor.temperature") -> None:
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


class EntityUnavailableError(SmartCoverError):
    """Entity is unavailable."""

    def __init__(self, entity_id: str) -> None:
        super().__init__(f"Entity '{entity_id}' is unavailable")
        self.entity_id = entity_id


class ConfigurationError(SmartCoverError):
    """Configuration is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Configuration error: {message}")
        self.message = message


class DataUpdateCoordinator(BaseCoordinator[dict[str, Any]]):
    """Class to manage cover automation."""

    config_entry: IntegrationConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: IntegrationConfigEntry
    ) -> None:
        super().__init__(
            hass,
            const.LOGGER,
            name=const.DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.config_entry = config_entry

        config = config_entry.runtime_data.config
        const.LOGGER.info(
            "Initializing Smart Cover Automation coordinator: mode=combined, covers=%s, update_interval=%s",
            config.get(const.CONF_COVERS, []),
            UPDATE_INTERVAL,
        )
        # Adjust logger level per-entry if verbose logging is enabled via options
        try:
            if bool(config.get(const.CONF_VERBOSE_LOGGING)):
                const.LOGGER.setLevel("DEBUG")
                const.LOGGER.debug("Verbose logging enabled for this entry")
        except Exception:  # pragma: no cover - non-critical
            pass

    async def _async_update_data(self) -> dict[str, Any]:
        """Update automation state and control covers."""
        try:
            config = self.config_entry.runtime_data.config
            covers = config[const.CONF_COVERS]

            const.LOGGER.info(
                "Starting cover automation update: mode=combined, covers=%s",
                covers,
            )

            if not covers:
                raise ConfigurationError("No covers configured for automation")

            if config.get(const.CONF_ENABLED) is False:
                const.LOGGER.info(
                    "Automation disabled via configuration; skipping actions"
                )
                return {"covers": {}}

            states = {
                entity_id: self.hass.states.get(entity_id) for entity_id in covers
            }

            available_covers = 0
            for entity_id, state in states.items():
                if state:
                    available_covers += 1
                else:
                    const.LOGGER.warning("Cover %s is unavailable", entity_id)

            if available_covers == 0:
                raise EntityUnavailableError("all_covers")

            return await self._handle_combined_automation(states, config)

        except SmartCoverError:
            raise
        except (KeyError, AttributeError) as err:
            raise ConfigurationError(str(err)) from err
        except (OSError, ValueError, TypeError) as err:
            raise UpdateFailed(f"System error during automation update: {err}") from err

    async def _set_cover_position(
        self, entity_id: str, desired_pos: int, features: int
    ) -> None:
        """Set cover position using best available method."""
        try:
            if features & CoverEntityFeature.SET_POSITION:
                const.LOGGER.info(
                    "Setting %s via set_cover_position to %d",
                    entity_id,
                    desired_pos,
                )
                const.LOGGER.info(
                    "[%s] Using set_cover_position to %d (features=%d)",
                    entity_id,
                    desired_pos,
                    features,
                )
                await self.hass.services.async_call(
                    "cover",
                    "set_cover_position",
                    {"entity_id": entity_id, "position": desired_pos},
                )
            elif desired_pos == COVER_FULLY_CLOSED:
                const.LOGGER.info("[%s] Closing cover", entity_id)
                await self.hass.services.async_call(
                    "cover", "close_cover", {"entity_id": entity_id}
                )
            elif desired_pos == COVER_FULLY_OPEN:
                const.LOGGER.info("[%s] Opening cover", entity_id)
                await self.hass.services.async_call(
                    "cover", "open_cover", {"entity_id": entity_id}
                )
            else:
                const.LOGGER.warning(
                    "Cannot set cover %s position: desired=%d, features=%d",
                    entity_id,
                    desired_pos,
                    features,
                )
        except (OSError, ValueError, TypeError, RuntimeError) as err:
            const.LOGGER.error("Failed to control cover %s: %s", entity_id, err)

    async def _handle_combined_automation(
        self,
        states: dict[str, State | None],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle combined temperature and sun automation."""
        result: dict[str, Any] = {"covers": {}}

        # Which contributors are configured
        temp_enabled = const.CONF_MAX_TEMP in config and const.CONF_MIN_TEMP in config
        sun_enabled = const.CONF_SUN_ELEVATION_THRESHOLD in config

        # Temperature input
        temp_available = False
        current_temp: float | None = None
        max_temp = float(config.get(const.CONF_MAX_TEMP, 0))
        min_temp = float(config.get(const.CONF_MIN_TEMP, 0))
        if temp_enabled:
            sensor_entity_id = config.get(
                const.CONF_TEMP_SENSOR, const.DEFAULT_TEMP_SENSOR
            )
            temp_state = self.hass.states.get(sensor_entity_id)
            if temp_state is None:
                # Required temp sensor missing -> captured as last_exception
                raise SensorNotFoundError(sensor_entity_id)
            try:
                current_temp = float(temp_state.state)
                temp_available = True
            except (ValueError, TypeError) as err:
                raise InvalidSensorReadingError(
                    temp_state.entity_id, str(temp_state.state)
                ) from err

        temp_hysteresis = float(
            config.get(const.CONF_TEMP_HYSTERESIS, const.TEMP_HYSTERESIS)
        )
        min_position_delta = int(
            float(config.get(const.CONF_MIN_POSITION_DELTA, const.MIN_POSITION_DELTA))
        )

        # Sun input
        sun_available = False
        elevation: float | None = None
        azimuth: float | None = None
        threshold = float(
            config.get(
                const.CONF_SUN_ELEVATION_THRESHOLD,
                const.DEFAULT_SUN_ELEVATION_THRESHOLD,
            )
        )
        if sun_enabled:
            sun_state = self.hass.states.get("sun.sun")
            if sun_state is None:
                # Required sun entity missing -> captured as last_exception
                raise UpdateFailed(ERR_NO_SUN)
            try:
                elevation = float(sun_state.attributes.get("elevation", 0))
                azimuth = float(sun_state.attributes.get("azimuth", 0))
                sun_available = True
            except (ValueError, TypeError) as err:
                raise UpdateFailed(ERR_INVALID_SUN) from err

        # Iterate covers
        for entity_id, state in states.items():
            if not state:
                const.LOGGER.warning("Skipping unavailable cover: %s", entity_id)
                continue

            features = state.attributes.get("supported_features", 0)
            current_pos = state.attributes.get("current_position")

            desired_from_temp: int | None = None
            desired_from_sun: int | None = None
            temp_hot: bool = False
            sun_hitting: bool = False
            details: dict[str, Any] = {}

            # Temperature contribution
            if temp_enabled and temp_available and current_temp is not None:
                if current_temp > max_temp + temp_hysteresis:
                    desired_from_temp = COVER_FULLY_CLOSED
                    temp_hot = True
                elif current_temp < min_temp - temp_hysteresis:
                    desired_from_temp = COVER_FULLY_OPEN
                else:
                    desired_from_temp = current_pos
                details.update(
                    {
                        "current_temp": current_temp,
                        "max_temp": max_temp,
                        "min_temp": min_temp,
                        "temp_hysteresis": temp_hysteresis,
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
            elif temp_enabled:
                details["temp_unavailable"] = True

            # Sun contribution
            if (
                sun_enabled
                and sun_available
                and elevation is not None
                and azimuth is not None
            ):
                direction = config.get(f"{entity_id}_{const.CONF_COVER_DIRECTION}")
                direction_azimuth: float | None = None
                if isinstance(direction, (int, float)):
                    try:
                        direction_azimuth = float(direction) % 360
                    except (TypeError, ValueError):
                        direction_azimuth = None
                elif isinstance(direction, str):
                    try:
                        direction_azimuth = float(direction) % 360
                    except (TypeError, ValueError):
                        direction_azimuth = None

                if direction_azimuth is not None:
                    # Compute sun desired position and whether the sun is hitting the window
                    angle_difference = None
                    if elevation >= threshold:
                        angle_difference = self._calculate_angle_difference(
                            azimuth, direction_azimuth
                        )
                        sun_hitting = angle_difference < const.AZIMUTH_TOLERANCE
                    else:
                        sun_hitting = False

                    desired_from_sun = self._calculate_desired_position(
                        elevation, azimuth, threshold, direction_azimuth, entity_id
                    )
                    details.update(
                        {
                            "sun_elevation": elevation,
                            "sun_azimuth": azimuth,
                            "elevation_threshold": threshold,
                            "window_direction": direction,
                            "window_direction_azimuth": direction_azimuth,
                            "angle_difference": angle_difference,
                            "desired_from_sun": desired_from_sun,
                            "sun_hitting": sun_hitting,
                        }
                    )
                    const.LOGGER.debug(
                        "Sun eval %s: elev=%.2f(threshold=%.2f) azimuth=%.2f window=%.2f angle_diff=%s hit=%s => desired_from_sun=%s",
                        entity_id,
                        elevation,
                        threshold,
                        azimuth,
                        direction_azimuth,
                        angle_difference,
                        sun_hitting,
                        desired_from_sun,
                    )
                else:
                    const.LOGGER.warning(
                        "Cover %s: invalid or missing direction for sun logic",
                        entity_id,
                    )
                    if not temp_enabled:
                        # Only sun configured -> skip this cover entirely
                        continue
                    details["sun_direction_invalid"] = True
            elif sun_enabled:
                details["sun_unavailable"] = True

            # Combine with logical AND semantics when both contributors are configured.
            # - If only temperature is configured: use temperature behavior.
            # - If only sun is configured: use sun behavior.
            # - If both are configured: move only when sun is hitting AND temperature is hot.
            combined_desired = current_pos
            if temp_enabled and sun_enabled:
                # Fallback: if sun direction invalid, behave as temperature-only
                if details.get("sun_direction_invalid"):
                    combined_desired = desired_from_temp
                elif temp_hot and sun_hitting and desired_from_sun is not None:
                    combined_desired = desired_from_sun
                else:
                    combined_desired = current_pos
            elif temp_enabled and not sun_enabled:
                combined_desired = desired_from_temp
            elif sun_enabled and not temp_enabled:
                combined_desired = desired_from_sun

            const.LOGGER.debug(
                "Combine %s: temp_enabled=%s sun_enabled=%s temp_hot=%s sun_hitting=%s desired_temp=%s desired_sun=%s => desired=%s",
                entity_id,
                temp_enabled,
                sun_enabled,
                temp_hot,
                sun_hitting,
                desired_from_temp,
                desired_from_sun,
                combined_desired,
            )

            # Act with min delta
            if (
                combined_desired is not None
                and current_pos is not None
                and combined_desired != current_pos
                and abs(combined_desired - current_pos) < min_position_delta
            ):
                const.LOGGER.debug(
                    "Skip small adjust %s: current=%s desired=%s delta=%s < min_delta=%s",
                    entity_id,
                    current_pos,
                    combined_desired,
                    abs(combined_desired - current_pos),
                    min_position_delta,
                )
            elif combined_desired is not None and combined_desired != current_pos:
                const.LOGGER.info(
                    "[%s] Action: current=%s desired=%s (features=%s)",
                    entity_id,
                    current_pos,
                    combined_desired,
                    features,
                )
                await self._set_cover_position(entity_id, combined_desired, features)

            details.update(
                {
                    "current_position": current_pos,
                    "desired_position": combined_desired,
                    "min_position_delta": min_position_delta,
                    "max_closure": int(
                        float(
                            self.config_entry.runtime_data.config.get(
                                const.CONF_MAX_CLOSURE, const.MAX_CLOSURE
                            )
                        )
                    ),
                    "combined_strategy": "and",
                }
            )

            result["covers"][entity_id] = details

        return result

    def _calculate_desired_position(
        self,
        elevation: float,
        azimuth: float,
        threshold: float,
        direction_azimuth: float,
        entity_id: str,
    ) -> int:
        """Calculate desired cover position for sun logic."""
        config = self.config_entry.runtime_data.config
        try:
            max_closure = int(
                float(config.get(const.CONF_MAX_CLOSURE, const.MAX_CLOSURE))
            )
        except (TypeError, ValueError):
            max_closure = const.MAX_CLOSURE

        if elevation < threshold:
            # Sun is low, open covers
            const.LOGGER.debug(
                "Desired %s (sun low): elevation=%.2f<threshold=%.2f => %d",
                entity_id,
                elevation,
                threshold,
                COVER_FULLY_OPEN,
            )
            return COVER_FULLY_OPEN

        # Calculate angle between sun and window
        angle_diff = self._calculate_angle_difference(azimuth, direction_azimuth)
        if angle_diff < const.AZIMUTH_TOLERANCE:
            desired_pos = max(COVER_FULLY_CLOSED, COVER_FULLY_OPEN - max_closure)
        else:
            desired_pos = COVER_FULLY_OPEN
        const.LOGGER.debug(
            "Desired %s (sun): angle_diff=%.2f tol=%d max_closure=%d => %d",
            entity_id,
            angle_diff,
            const.AZIMUTH_TOLERANCE,
            max_closure,
            desired_pos,
        )
        return round(desired_pos)

    def _calculate_angle_difference(
        self, azimuth: float, direction_azimuth: float
    ) -> float:
        """Calculate minimal absolute angle difference between two azimuths."""
        return abs(((azimuth - direction_azimuth + 180) % 360) - 180)
