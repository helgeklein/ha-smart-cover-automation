"""
Smart cover automation coordinator.

This module provides automation logic for controlling covers based on
temperature and sun position.
"""

from __future__ import annotations

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
    MAX_CLOSURE,
)

if TYPE_CHECKING:
    from homeassistant.core import State

    from .data import IntegrationConfigEntry

# Constants
COVER_FULLY_OPEN: Final = 100
COVER_FULLY_CLOSED: Final = 0
UPDATE_INTERVAL: Final = 60

# Error messages
ERR_NO_TEMP_SENSOR = "Temperature sensor not found"
ERR_INVALID_TEMP = "Invalid temperature reading"
ERR_NO_SUN = "Sun integration not found"
ERR_INVALID_SUN = "Invalid sun position data"

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

    def __init__(self) -> None:
        """Initialize sensor not found error."""
        super().__init__(ERR_NO_TEMP_SENSOR)


class InvalidSensorReadingError(SmartCoverError):
    """Invalid sensor reading received."""

    def __init__(self) -> None:
        """Initialize invalid sensor reading error."""
        super().__init__(ERR_INVALID_TEMP)


class DataUpdateCoordinator(BaseCoordinator[dict[str, Any]]):
    """Class to manage cover automation."""

    config_entry: IntegrationConfigEntry

    async def _async_update_data(self) -> dict[str, Any]:
        """Update automation state and control covers."""
        config = self.config_entry.runtime_data.config
        automation_type = config[CONF_AUTOMATION_TYPE]
        covers = config[CONF_COVERS]

        # Get current states
        states = {entity_id: self.hass.states.get(entity_id) for entity_id in covers}

        if automation_type == AUTOMATION_TYPE_TEMPERATURE:
            return await self._handle_temperature_automation(states, config)

        if automation_type == AUTOMATION_TYPE_SUN:
            return await self._handle_sun_automation(states)

        return {"error": "Unknown automation type"}

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
            raise SensorNotFoundError from None

        try:
            current_temp = float(temp_sensor.state)
        except (ValueError, TypeError) as err:
            raise InvalidSensorReadingError from err

        max_temp = config[CONF_MAX_TEMP]
        min_temp = config[CONF_MIN_TEMP]

        for entity_id, state in states.items():
            if not state:
                continue

            features = state.attributes.get("supported_features", 0)
            current_pos = state.attributes.get("current_position", None)

            # Determine desired position based on temperature
            if current_temp > max_temp:
                desired_pos = COVER_FULLY_CLOSED  # Close to block heat
            elif current_temp < min_temp:
                desired_pos = COVER_FULLY_OPEN  # Open to allow heat
            else:
                desired_pos = current_pos  # Maintain current position

            if desired_pos is not None and desired_pos != current_pos:
                await self._set_cover_position(entity_id, desired_pos, features)

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
        if features & CoverEntityFeature.SET_POSITION:
            await self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": entity_id, "position": desired_pos},
            )
        elif desired_pos == COVER_FULLY_CLOSED:
            await self.hass.services.async_call(
                "cover",
                "close_cover",
                {"entity_id": entity_id},
            )
        elif desired_pos == COVER_FULLY_OPEN:
            await self.hass.services.async_call(
                "cover",
                "open_cover",
                {"entity_id": entity_id},
            )

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
            msg = ERR_NO_SUN
            raise UpdateFailed(msg)

        try:
            elevation = float(sun_state.attributes.get("elevation", 0))
            azimuth = float(sun_state.attributes.get("azimuth", 0))
        except (ValueError, TypeError) as err:
            msg = ERR_INVALID_SUN
            raise UpdateFailed(msg) from err

        # Get config
        config = self.config_entry.runtime_data.config
        threshold = config.get(
            CONF_SUN_ELEVATION_THRESHOLD, DEFAULT_SUN_ELEVATION_THRESHOLD
        )

        for entity_id, state in states.items():
            if not state:
                continue

            # Get cover settings
            features = state.attributes.get("supported_features", 0)
            current_pos = state.attributes.get("current_position", None)
            direction = config.get(f"{entity_id}_{CONF_COVER_DIRECTION}")

            if direction is None:
                continue

            direction_azimuth = DIRECTION_TO_AZIMUTH.get(direction)

            if direction_azimuth is None:
                continue  # Skip if direction not set

            # Calculate position based on sun position
            desired_pos = self._calculate_desired_position(
                elevation, azimuth, threshold, direction_azimuth
            )

            if desired_pos != current_pos:
                await self._set_cover_position(entity_id, desired_pos, features)

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
