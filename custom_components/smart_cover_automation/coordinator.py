"""
Smart cover automation coordinator.

This module provides automation logic for controlling covers based on
temperature and sun position.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator as BaseCoordinator,
)
from homeassistant.helpers.update_coordinator import (
    UpdateFailed,
)

from .const import (
    AUTOMATION_TYPE_SUN,
    AUTOMATION_TYPE_TEMPERATURE,
    AZIMUTH_TOLERANCE,
    CONF_AUTOMATION_TYPE,
    CONF_COVER_DIRECTION,
    CONF_COVERS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SUN_ELEVATION_THRESHOLD,
    DEFAULT_SUN_ELEVATION_THRESHOLD,
    DIRECTION_EAST,
    DIRECTION_NORTH,
    DIRECTION_NORTHEAST,
    DIRECTION_NORTHWEST,
    DIRECTION_SOUTH,
    DIRECTION_SOUTHEAST,
    DIRECTION_SOUTHWEST,
    DIRECTION_WEST,
    DOMAIN,
    LOGGER,
    MAX_CLOSURE,
)

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

# Direction to azimuth mapping
DIRECTION_TO_AZIMUTH = {
    DIRECTION_NORTH: 0,
    DIRECTION_NORTHEAST: 45,
    DIRECTION_EAST: 90,
    DIRECTION_SOUTHEAST: 135,
    DIRECTION_SOUTH: 180,
    DIRECTION_SOUTHWEST: 225,
    DIRECTION_WEST: 270,
    DIRECTION_NORTHWEST: 315,
}


class SmartCoverError(UpdateFailed):
    """Base class for smart cover automation errors."""


class SensorNotFoundError(SmartCoverError):
    """Temperature sensor could not be found."""

    def __init__(self, sensor_name: str = "sensor.temperature") -> None:
        """Initialize sensor not found error."""
        super().__init__(f"Temperature sensor '{sensor_name}' not found")
        self.sensor_name = sensor_name


class InvalidSensorReadingError(SmartCoverError):
    """Invalid sensor reading received."""

    def __init__(self, sensor_name: str, value: str) -> None:
        """Initialize invalid sensor reading error."""
        super().__init__(f"Invalid reading from '{sensor_name}': {value}")
        self.sensor_name = sensor_name
        self.value = value


class ServiceCallError(SmartCoverError):
    """Service call failed."""

    def __init__(self, service: str, entity_id: str, error: str) -> None:
        """Initialize service call error."""
        super().__init__(f"Failed to call {service} for {entity_id}: {error}")
        self.service = service
        self.entity_id = entity_id
        self.error = error


class EntityUnavailableError(SmartCoverError):
    """Entity is unavailable."""

    def __init__(self, entity_id: str) -> None:
        """Initialize entity unavailable error."""
        super().__init__(f"Entity '{entity_id}' is unavailable")
        self.entity_id = entity_id


class ConfigurationError(SmartCoverError):
    """Configuration is invalid."""

    def __init__(self, message: str) -> None:
        """Initialize configuration error."""
        super().__init__(f"Configuration error: {message}")
        self.message = message


class DataUpdateCoordinator(BaseCoordinator[dict[str, Any]]):
    """Class to manage cover automation."""

    config_entry: IntegrationConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: IntegrationConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.config_entry = config_entry

        config = config_entry.runtime_data.config
        LOGGER.info(
            "Initializing Smart Cover Automation coordinator: "
            "type=%s, covers=%s, update_interval=%s",
            config.get(CONF_AUTOMATION_TYPE),
            config.get(CONF_COVERS, []),
            UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update automation state and control covers."""
        try:
            config = self.config_entry.runtime_data.config
            automation_type = config[CONF_AUTOMATION_TYPE]
            covers = config[CONF_COVERS]

            LOGGER.info(
                "Starting cover automation update: type=%s, covers=%s",
                automation_type,
                covers,
            )

            # Validate configuration
            if not covers:
                error_msg = "No covers configured for automation"
                raise ConfigurationError(error_msg)

            # Get current states
            states = {
                entity_id: self.hass.states.get(entity_id) for entity_id in covers
            }

            # Log current cover states and check availability
            available_covers = 0
            for entity_id, state in states.items():
                if state:
                    current_pos = state.attributes.get("current_position")
                    LOGGER.debug(
                        "Cover %s current state: position=%s, state=%s",
                        entity_id,
                        current_pos,
                        state.state,
                    )
                    available_covers += 1
                else:
                    LOGGER.warning("Cover %s is unavailable", entity_id)

            # Ensure at least one cover is available
            if available_covers == 0:
                error_msg = "All configured covers are unavailable"
                LOGGER.error(error_msg)
                all_covers_entity = "all_covers"
                raise EntityUnavailableError(all_covers_entity)

            if automation_type == AUTOMATION_TYPE_TEMPERATURE:
                LOGGER.debug("Using temperature-based automation")
                return await self._handle_temperature_automation(states, config)

            if automation_type == AUTOMATION_TYPE_SUN:
                LOGGER.debug("Using sun-based automation")
                return await self._handle_sun_automation(states)

            LOGGER.error("Unknown automation type: %s", automation_type)
            error_msg = f"Unknown automation type: {automation_type}"
            raise ConfigurationError(error_msg)

        except SmartCoverError:
            # Re-raise our custom errors
            raise
        except (KeyError, AttributeError) as err:
            error_msg = f"Configuration error: {err}"
            LOGGER.error("Configuration validation failed: %s", error_msg)
            raise ConfigurationError(str(err)) from err
        except (OSError, ValueError, TypeError) as err:
            error_msg = f"System error during automation update: {err}"
            LOGGER.error(error_msg)
            raise UpdateFailed(error_msg) from err

    async def _handle_temperature_automation(
        self,
        states: dict[str, State | None],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle temperature-based automation."""
        result = {"covers": {}}

        # Get temperature from climate entity or sensor
        temp_sensor = self.hass.states.get("sensor.temperature")  # Configure this
        if not temp_sensor:
            LOGGER.error("Temperature sensor 'sensor.temperature' not found")
            sensor_name = "sensor.temperature"
            raise SensorNotFoundError(sensor_name) from None

        try:
            current_temp = float(temp_sensor.state)
        except (ValueError, TypeError) as err:
            LOGGER.error(
                "Invalid temperature reading from %s: %s",
                temp_sensor.entity_id,
                temp_sensor.state,
            )
            raise InvalidSensorReadingError(
                temp_sensor.entity_id, str(temp_sensor.state)
            ) from err

        max_temp = config[CONF_MAX_TEMP]
        min_temp = config[CONF_MIN_TEMP]

        LOGGER.info(
            "Temperature automation: current=%.1f°C, range=%.1f-%.1f°C",
            current_temp,
            min_temp,
            max_temp,
        )

        for entity_id, state in states.items():
            if not state:
                LOGGER.warning("Skipping unavailable cover: %s", entity_id)
                continue

            features = state.attributes.get("supported_features", 0)
            current_pos = state.attributes.get("current_position", None)

            # Determine desired position based on temperature
            if current_temp > max_temp:
                desired_pos = COVER_FULLY_CLOSED  # Close to block heat
                reason = (
                    f"Too hot ({current_temp:.1f}°C > {max_temp}°C) - "
                    "closing to block heat"
                )
            elif current_temp < min_temp:
                desired_pos = COVER_FULLY_OPEN  # Open to allow heat
                reason = (
                    f"Too cold ({current_temp:.1f}°C < {min_temp}°C) - "
                    "opening to allow heat"
                )
            else:
                desired_pos = current_pos  # Maintain current position
                reason = (
                    f"Temperature comfortable ({current_temp:.1f}°C in range "
                    f"{min_temp}-{max_temp}°C) - maintaining position"
                )

            LOGGER.info(
                "Cover %s: %s (current: %s → desired: %s)",
                entity_id,
                reason,
                current_pos,
                desired_pos,
            )

            if desired_pos is not None and desired_pos != current_pos:
                LOGGER.info(
                    "Setting cover %s position from %s to %s",
                    entity_id,
                    current_pos,
                    desired_pos,
                )
                await self._set_cover_position(entity_id, desired_pos, features)
            else:
                LOGGER.debug("Cover %s: no position change needed", entity_id)

            result["covers"][entity_id] = {
                "current_temp": current_temp,
                "max_temp": max_temp,
                "min_temp": min_temp,
                "current_position": current_pos,
                "desired_position": desired_pos,
            }

        return result

    async def _set_cover_position(
        self, entity_id: str, desired_pos: int, features: int
    ) -> None:
        """Set cover position using best available method."""
        try:
            if features & CoverEntityFeature.SET_POSITION:
                LOGGER.debug(
                    "Setting cover %s to position %d using set_cover_position service",
                    entity_id,
                    desired_pos,
                )
                await self.hass.services.async_call(
                    "cover",
                    "set_cover_position",
                    {"entity_id": entity_id, "position": desired_pos},
                )
            elif desired_pos == COVER_FULLY_CLOSED:
                LOGGER.debug(
                    "Closing cover %s using close_cover service (no position support)",
                    entity_id,
                )
                await self.hass.services.async_call(
                    "cover",
                    "close_cover",
                    {"entity_id": entity_id},
                )
            elif desired_pos == COVER_FULLY_OPEN:
                LOGGER.debug(
                    "Opening cover %s using open_cover service (no position support)",
                    entity_id,
                )
                await self.hass.services.async_call(
                    "cover",
                    "open_cover",
                    {"entity_id": entity_id},
                )
            else:
                LOGGER.warning(
                    "Cannot set cover %s position: desired=%d, features=%d",
                    entity_id,
                    desired_pos,
                    features,
                )
        except (OSError, ValueError, TypeError, RuntimeError) as err:
            error_msg = f"Service call failed: {err}"
            LOGGER.error(
                "Failed to control cover %s: %s (desired_pos=%d, features=%d)",
                entity_id,
                error_msg,
                desired_pos,
                features,
            )
            # Don't raise - continue with other covers
            # We just log the error for debugging

    def _calculate_angle_difference(
        self, azimuth: float, direction_azimuth: float
    ) -> float:
        """Calculate angle difference between sun and window direction."""
        return abs(((azimuth - direction_azimuth + 180) % 360) - 180)

    async def _handle_sun_automation(
        self,
        states: dict[str, State | None],
    ) -> dict[str, Any]:
        """Handle sun-based automation."""
        result = {"covers": {}}

        # Get sun position
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            LOGGER.error("Sun integration not available - sun.sun entity not found")
            msg = ERR_NO_SUN
            raise UpdateFailed(msg)

        try:
            elevation = float(sun_state.attributes.get("elevation", 0))
            azimuth = float(sun_state.attributes.get("azimuth", 0))
        except (ValueError, TypeError) as err:
            LOGGER.error(
                "Invalid sun position data: elevation=%s, azimuth=%s",
                sun_state.attributes.get("elevation"),
                sun_state.attributes.get("azimuth"),
            )
            msg = ERR_INVALID_SUN
            raise UpdateFailed(msg) from err

        # Get config
        config = self.config_entry.runtime_data.config
        threshold = config.get(
            CONF_SUN_ELEVATION_THRESHOLD, DEFAULT_SUN_ELEVATION_THRESHOLD
        )

        LOGGER.info(
            "Sun automation: elevation=%.1f°, azimuth=%.1f°, threshold=%.1f°",
            elevation,
            azimuth,
            threshold,
        )

        for entity_id, state in states.items():
            if not state:
                LOGGER.warning("Skipping unavailable cover: %s", entity_id)
                continue

            # Get cover settings
            features = state.attributes.get("supported_features", 0)
            current_pos = state.attributes.get("current_position", None)
            direction = config.get(f"{entity_id}_{CONF_COVER_DIRECTION}")

            if direction is None:
                LOGGER.warning(
                    "Cover %s: no direction configured, skipping sun automation",
                    entity_id,
                )
                continue

            direction_azimuth = DIRECTION_TO_AZIMUTH.get(direction)

            if direction_azimuth is None:
                LOGGER.error(
                    "Cover %s: invalid direction '%s', skipping sun automation",
                    entity_id,
                    direction,
                )
                continue  # Skip if direction not set

            LOGGER.debug(
                "Cover %s: direction=%s (%.0f°), current_pos=%s",
                entity_id,
                direction,
                direction_azimuth,
                current_pos,
            )

            # Calculate position based on sun position
            desired_pos = self._calculate_desired_position_with_logging(
                elevation, azimuth, threshold, direction_azimuth, entity_id
            )

            LOGGER.info(
                "Cover %s: current=%s → desired=%s",
                entity_id,
                current_pos,
                desired_pos,
            )

            if desired_pos != current_pos:
                LOGGER.info(
                    "Setting cover %s position from %s to %s",
                    entity_id,
                    current_pos,
                    desired_pos,
                )
                await self._set_cover_position(entity_id, desired_pos, features)
            else:
                LOGGER.debug("Cover %s: no position change needed", entity_id)

            # Calculate angle_diff for result
            angle_difference = None
            if elevation >= threshold:
                angle_difference = self._calculate_angle_difference(
                    azimuth, direction_azimuth
                )

            result["covers"][entity_id] = {
                "sun_elevation": elevation,
                "sun_azimuth": azimuth,
                "elevation_threshold": threshold,
                "window_direction": direction,
                "angle_difference": angle_difference,
                "current_position": current_pos,
                "desired_position": desired_pos,
            }

        return result

    def _calculate_desired_position_with_logging(
        self,
        elevation: float,
        azimuth: float,
        threshold: float,
        direction_azimuth: float,
        entity_id: str,
    ) -> int:
        """Calculate desired cover position with detailed logging."""
        if elevation < threshold:
            # Sun is low, open covers
            LOGGER.info(
                "Cover %s: Sun low (%.1f° < %.1f°) - opening fully",
                entity_id,
                elevation,
                threshold,
            )
            return COVER_FULLY_OPEN

        # Calculate angle between sun and window
        angle_diff = self._calculate_angle_difference(azimuth, direction_azimuth)

        LOGGER.debug(
            "Cover %s: Sun above threshold - elevation=%.1f°, "
            "sun_azimuth=%.1f°, window_azimuth=%.1f°, angle_diff=%.1f°",
            entity_id,
            elevation,
            azimuth,
            direction_azimuth,
            angle_diff,
        )

        if angle_diff <= AZIMUTH_TOLERANCE:
            # Sun is hitting window - calculate closure based on angle
            # Direct hit (0°) = MAX_CLOSURE
            # AZIMUTH_TOLERANCE° = minimal closure
            factor = 1 - (angle_diff / AZIMUTH_TOLERANCE)
            desired_pos = COVER_FULLY_OPEN - (MAX_CLOSURE * factor)

            LOGGER.info(
                "Cover %s: Sun hitting window (angle=%.1f° ≤ %.1f°) - "
                "partial closure factor=%.2f, position=%d",
                entity_id,
                angle_diff,
                AZIMUTH_TOLERANCE,
                factor,
                round(desired_pos),
            )
        else:
            # Sun not hitting this window
            desired_pos = COVER_FULLY_OPEN
            LOGGER.info(
                "Cover %s: Sun not hitting window (angle=%.1f° > %.1f°) - "
                "opening fully",
                entity_id,
                angle_diff,
                AZIMUTH_TOLERANCE,
            )

        # Round to nearest whole number
        return round(desired_pos)

    def _calculate_desired_position(
        self,
        elevation: float,
        azimuth: float,
        threshold: float,
        direction_azimuth: float,
    ) -> int:
        """Calculate desired cover position based on sun position."""
        if elevation < threshold:
            # Sun is low, open covers
            return COVER_FULLY_OPEN

        # Calculate angle between sun and window
        angle_diff = self._calculate_angle_difference(azimuth, direction_azimuth)

        if angle_diff <= AZIMUTH_TOLERANCE:
            # Sun is hitting window - calculate closure based on angle
            # Direct hit (0°) = MAX_CLOSURE
            # AZIMUTH_TOLERANCE° = minimal closure
            factor = 1 - (angle_diff / AZIMUTH_TOLERANCE)
            desired_pos = COVER_FULLY_OPEN - (MAX_CLOSURE * factor)
        else:
            # Sun not hitting this window
            desired_pos = COVER_FULLY_OPEN

        # Round to nearest whole number
        return round(desired_pos)
