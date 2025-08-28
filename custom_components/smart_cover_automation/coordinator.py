"""
DataUpdateCoordinator for smart_cover_automation.

This module implements the core automation logic for smart cover control.
It supports two automation modes:

1. Temperature-based:
   - Monitors temperature sensor
   - Closes covers when too hot
   - Opens covers when too cold
   - Maintains position in comfort range

2. Sun-based:
   - Tracks sun position (elevation and azimuth)
   - Considers window orientation
   - Manages covers to block direct sun while maximizing natural light
   - Opens fully when sun is low or not hitting window
   - Closes proportionally when sun hits window directly

For detailed implementation notes, see the docstrings of individual methods
and the README.md file.
"""

"""Smart cover automation coordinator.

This module provides automation logic for controlling covers based on
temperature and sun position.
"""

from __future__ import annotations

from typing import Any, Final, Optional, TYPE_CHECKING, cast

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity import get_capability
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator as BaseCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import utcnow

from .const import (
    AUTOMATION_TYPE_SUN,
    AUTOMATION_TYPE_TEMPERATURE,
    AZIMUTH_TOLERANCE,
    CONF_AUTOMATION_TYPE,
    CONF_COVER_DIRECTION,
    CONF_COVER_ENTITY,
    CONF_COVERS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_TEMP_SENSOR,
    DIRECTION_TO_AZIMUTH,
    DOMAIN,
)

# Constants
COVER_FULLY_OPEN: Final = 100  # % fully open
COVER_FULLY_CLOSED: Final = 0  # % fully closed
UPDATE_INTERVAL: Final = 60  # seconds
COVER_POSITIONS: Final = {
    "open": COVER_FULLY_OPEN,
    "closed": COVER_FULLY_CLOSED,
}


class SmartCoverError(UpdateFailed):
    """Base class for smart cover automation errors."""


class SensorNotFoundError(SmartCoverError):
    """Temperature sensor could not be found."""

    def __init__(self) -> None:
        """Initialize sensor not found error."""
        super().__init__("Temperature sensor not found")


class InvalidSensorReadingError(SmartCoverError):
    """Invalid sensor reading received."""

    def __init__(self) -> None:
        """Initialize invalid sensor reading error."""
        super().__init__("Invalid temperature reading")


class DataUpdateCoordinator(BaseCoordinator[dict[str, Any]]):
    """Class to manage fetching data about the cover state."""


from __future__ import annotations

from typing import TYPE_CHECKING, Any

# pylint: disable=too-many-branches
from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from homeassistant.core import State

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

# Constants
FULLY_OPEN = 100
FULLY_CLOSED = 0

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

if TYPE_CHECKING:
    from .data import IntegrationConfigEntry


class DataUpdateCoordinator(DataUpdateCoordinator):
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
        elif automation_type == AUTOMATION_TYPE_SUN:
            return await self._handle_sun_automation(states)

        return {"error": "Unknown automation type"}

    async def _handle_temperature_automation(
        self,
        states: dict[str, State],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle temperature-based automation."""
        result = {"covers": {}}

        # Get temperature from climate entity or sensor
        temp_sensor = self.hass.states.get("sensor.temperature")  # Configure this
        if not temp_sensor:
            raise UpdateFailed("Temperature sensor not found")

        try:
            current_temp = float(temp_sensor.state)
        except (ValueError, TypeError):
            raise UpdateFailed("Invalid temperature reading")

        max_temp = config[CONF_MAX_TEMP]
        min_temp = config[CONF_MIN_TEMP]

        for entity_id, state in states.items():
            if not state:
                continue

            features = state.attributes.get("supported_features", 0)
            current_pos = state.attributes.get("current_position", None)

            # Determine desired position based on temperature
            if current_temp > max_temp:
                desired_pos = 0  # Close to block heat
            elif current_temp < min_temp:
                desired_pos = 100  # Open to allow heat
            else:
                desired_pos = current_pos  # Maintain current position

            if desired_pos != current_pos:
                # Set cover position or use open/close
                if features & CoverEntityFeature.SET_POSITION:
                    await self.hass.services.async_call(
                        "cover",
                        "set_cover_position",
                        {"entity_id": entity_id, "position": desired_pos},
                    )
                elif desired_pos == 0:
                    await self.hass.services.async_call(
                        "cover",
                        "close_cover",
                        {"entity_id": entity_id},
                    )
                elif desired_pos == 100:
                    await self.hass.services.async_call(
                        "cover",
                        "open_cover",
                        {"entity_id": entity_id},
                    )

            result["covers"][entity_id] = {
                "current_temp": current_temp,
                "max_temp": max_temp,
                "min_temp": min_temp,
                "current_position": current_pos,
                "desired_position": desired_pos,
            }

        return result

    async def _handle_sun_automation(
        self,
        states: dict[str, State],
    ) -> dict[str, Any]:
        """
        Handle sun-based automation.

        Controls covers based on sun position relative to windows:
        1. Sun elevation (height in sky) determines if covers need adjustment
        2. Sun azimuth (compass direction) determines how much to close
        3. Cover direction (window orientation) affects sun impact

        Algorithm:
        - Below elevation threshold: open covers
        - Above threshold:
          - Direct sun: close proportionally to sun angle
          - No direct sun: open fully
        """
        result = {"covers": {}}

        # Get sun position
        sun_state = self.hass.states.get("sun.sun")
        if not sun_state:
            raise UpdateFailed(ERR_NO_SUN)

        try:
            elevation = float(sun_state.attributes.get("elevation", 0))
            azimuth = float(sun_state.attributes.get("azimuth", 0))
        except (ValueError, TypeError) as err:
            raise UpdateFailed(ERR_INVALID_SUN) from err

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
            direction_azimuth = DIRECTION_TO_AZIMUTH.get(direction)

            if direction_azimuth is None:
                continue  # Skip if direction not set

            # Calculate position based on sun position
            if elevation < threshold:
                # Sun is low, open covers
                desired_pos = FULLY_OPEN
            else:
                # Calculate angle between sun and window
                angle_diff = abs(((azimuth - direction_azimuth + 180) % 360) - 180)

                if angle_diff <= AZIMUTH_TOLERANCE:
                    # Sun is hitting window - calculate closure based on angle
                    # Direct hit (0°) = MAX_CLOSURE
                    # AZIMUTH_TOLERANCE° = minimal closure
                    factor = 1 - (angle_diff / AZIMUTH_TOLERANCE)
                    desired_pos = FULLY_OPEN - (MAX_CLOSURE * factor)
                else:
                    # Sun not hitting this window
                    desired_pos = FULLY_OPEN

            # Round to nearest whole number
            desired_pos = round(desired_pos)

            if desired_pos != current_pos:
                # Set cover position or use open/close
                if features & CoverEntityFeature.SET_POSITION:
                    await self.hass.services.async_call(
                        "cover",
                        "set_cover_position",
                        {"entity_id": entity_id, "position": desired_pos},
                    )
                elif desired_pos == FULLY_CLOSED:
                    await self.hass.services.async_call(
                        "cover",
                        "close_cover",
                        {"entity_id": entity_id},
                    )
                elif desired_pos == FULLY_OPEN:
                    await self.hass.services.async_call(
                        "cover",
                        "open_cover",
                        {"entity_id": entity_id},
                    )

            result["covers"][entity_id] = {
                "sun_elevation": elevation,
                "sun_azimuth": azimuth,
                "elevation_threshold": threshold,
                "window_direction": direction,
                "angle_difference": angle_diff if "angle_diff" in locals() else None,
                "current_position": current_pos,
                "desired_position": desired_pos,
            }

        return result
