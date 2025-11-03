"""Cover automation logic for individual covers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, assert_never

from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from . import const
from .config import ResolvedConfig
from .cover_position_history import CoverPositionHistoryManager
from .util import to_float_or_none, to_int_or_none

if TYPE_CHECKING:
    from homeassistant.core import State


class CoverMovementReason(Enum):
    """Encapsulates cover movement and reason."""

    CLOSING_HEAT_PROTECTION = "closing_heat_protection"
    OPENING_LET_LIGHT_IN = "opening_let_light_in"
    CLOSING_AFTER_SUNSET = "closing_after_sunset"


@dataclass
class SensorData:
    """Encapsulates sensor data gathered for an automation run."""

    sun_azimuth: float
    sun_elevation: float
    temp_max: float
    temp_hot: bool
    weather_condition: str
    weather_sunny: bool
    should_close_for_sunset: bool  # True only in the ONE update cycle when covers should close after sunset


class CoverAutomation:
    """Handles automation logic for a single cover."""

    #
    # __init__
    #
    def __init__(
        self,
        entity_id: str,
        resolved: ResolvedConfig,
        config: dict[str, Any],
        cover_pos_history_mgr: CoverPositionHistoryManager,
        ha_interface: Any,
    ) -> None:
        """Initialize cover automation.

        Args:
            entity_id: Cover entity ID
            resolved: Resolved configuration settings
            config: Raw configuration dictionary
            cover_pos_history_mgr: Cover position history manager
            ha_interface: Home Assistant interface for API interactions
        """

        self.entity_id = entity_id
        self.resolved = resolved
        self.config = config
        self._cover_pos_history_mgr = cover_pos_history_mgr
        self._ha_interface = ha_interface

    #
    # process
    #
    async def process(self, state: State | None, sensor_data: SensorData) -> dict[str, Any]:
        """Process automation for this cover.

        Args:
            state: Current state of the cover
            sensor_data: Gathered sensor data

        Returns:
            Dictionary of cover attributes
        """

        cover_attrs: dict[str, Any] = {}

        # Get cover azimuth
        cover_azimuth = self._get_cover_azimuth()
        if cover_azimuth is None:
            return cover_attrs
        else:
            cover_attrs[const.COVER_ATTR_COVER_AZIMUTH] = cover_azimuth

        # Validate current cover state
        if not self._validate_cover_state(state):
            return cover_attrs
        else:
            # At this point, we know state is not None due to validation (type narrowing for type checkers)
            assert state is not None
            cover_attrs[const.COVER_ATTR_STATE] = state.state

        # Check if cover is moving
        if self._is_cover_moving(state):
            return cover_attrs

        # Get cover features
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        cover_attrs[const.COVER_ATTR_SUPPORTED_FEATURES] = features

        # Get cover position
        success, current_pos = self._get_cover_position(state, features)
        if not success:
            return cover_attrs
        else:
            cover_attrs[const.COVER_ATTR_POS_CURRENT] = current_pos

        # Check for manual override
        if self._check_manual_override(current_pos):
            return cover_attrs

        # Calculate sun hitting
        sun_hitting, sun_azimuth_difference = self._calculate_sun_hitting(sensor_data.sun_azimuth, sensor_data.sun_elevation, cover_azimuth)
        cover_attrs[const.COVER_ATTR_SUN_HITTING] = sun_hitting
        cover_attrs[const.COVER_ATTR_SUN_AZIMUTH_DIFF] = sun_azimuth_difference

        # Calculate desired position
        desired_pos, movement_reason = self._calculate_desired_position(sensor_data, sun_hitting)
        cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = desired_pos

        # Check for lockout protection (window sensors)
        lockout_protection = self._check_lockout_protection(movement_reason)
        cover_attrs[const.COVER_ATTR_LOCKOUT_PROTECTION] = lockout_protection
        if lockout_protection:
            return cover_attrs

        # Move cover if needed
        movement_needed, actual_pos, message = await self._move_cover_if_needed(current_pos, desired_pos, features, movement_reason)
        if not movement_needed:
            # No movement - just add the current position to the history
            self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
        else:
            # Movement occurred
            cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = actual_pos

        # Include position history in cover attributes
        position_entries = self._cover_pos_history_mgr.get_entries(self.entity_id)
        cover_attrs[const.COVER_ATTR_POS_HISTORY] = [entry.position for entry in position_entries]

        # Log per-cover attributes
        const.LOGGER.debug(f"[{self.entity_id}] Cover result: {message}. Cover data: {str(cover_attrs)}")

        return cover_attrs

    #
    # _get_cover_azimuth
    #
    def _get_cover_azimuth(self) -> float | None:
        """Get and validate cover azimuth from configuration.

        Args:
            cover_attrs: Dictionary to store cover attributes

        Returns:
            Cover azimuth or None if invalid/missing
        """
        cover_azimuth_raw = self.config.get(f"{self.entity_id}_{const.COVER_SFX_AZIMUTH}")
        cover_azimuth = to_float_or_none(cover_azimuth_raw)
        if cover_azimuth is None:
            self._log_cover_msg("Cover has invalid or missing azimuth (direction), skipping", const.LogSeverity.INFO)
            return None
        return cover_azimuth

    #
    # _validate_cover_state
    #
    def _validate_cover_state(self, state: State | None) -> bool:
        """Validate cover state is usable for automation.

        Args:
            state: Cover state
            cover_attrs: Dictionary to store cover attributes

        Returns:
            True if state is valid, False otherwise
        """

        if state is None or state.state is None:
            self._log_cover_msg("Cover state unavailable, skipping", const.LogSeverity.INFO)
            return False
        if state.state in ("", STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._log_cover_msg(f"Cover state '{state.state}' unsupported, skipping", const.LogSeverity.INFO)
            return False
        return True

    #
    # _is_cover_moving
    #
    def _is_cover_moving(self, state: State) -> bool:
        """Check if cover is currently moving.

        Args:
            state: Cover state
            cover_attrs: Dictionary to store cover attributes

        Returns:
            True if cover is moving, False otherwise
        """

        is_moving = state.state.lower() in (STATE_OPENING, STATE_CLOSING)
        if is_moving:
            self._log_cover_msg("Cover is currently moving, skipping", const.LogSeverity.INFO)
        return is_moving

    #
    # _check_lockout_protection
    #
    def _check_lockout_protection(self, movement_reason: CoverMovementReason) -> bool:
        """Check if lockout protection should be enforced for this cover.

        Lockout protection prevents cover closing when associated window sensors indicate
        that a window is open.

        Returns:
            True if lockout is active (should skip), False otherwise
        """

        # Get configured window sensors for this cover
        window_sensors_key = f"{self.entity_id}_{const.COVER_SFX_WINDOW_SENSORS}"
        window_sensors = self.config.get(window_sensors_key)

        # If no window sensors configured, no lockout protection needed
        if not window_sensors or not isinstance(window_sensors, list):
            return False

        # Check if any window sensor indicates an open window
        open_sensors = []
        for sensor_id in window_sensors:
            sensor_state = self._ha_interface.get_entity_state(sensor_id)
            if sensor_state == STATE_ON:
                open_sensors.append(sensor_id)

        # If any window is open, activate lockout protection
        if open_sensors and movement_reason == CoverMovementReason.CLOSING_HEAT_PROTECTION:
            self._log_cover_msg("Lockout protection active, skipping closing", const.LogSeverity.INFO)
            return True

        return False

    #
    # _get_cover_position
    #
    def _get_cover_position(self, state: State, features: int) -> tuple[bool, int]:
        """Get current cover position.

        Args:
            state: Cover state
            features: Cover supported features

        Returns:
            Current position (0-100)
        """

        if features & CoverEntityFeature.SET_POSITION:
            # Cover supports position control
            pos = to_int_or_none(state.attributes.get(ATTR_CURRENT_POSITION))
            if pos is not None:
                return True, pos
            else:
                self._log_cover_msg("Cover supports position but position attribute is missing or invalid", const.LogSeverity.INFO)
                return False, const.COVER_POS_FULLY_OPEN

        # Cover does not support position - infer from state
        cover_state = state.state.lower() if state.state else None
        if cover_state == STATE_CLOSED:
            return True, const.COVER_POS_FULLY_CLOSED
        elif cover_state == STATE_OPEN:
            return True, const.COVER_POS_FULLY_OPEN
        else:
            # Unknown state
            return False, const.COVER_POS_FULLY_OPEN

    #
    # _check_manual_override
    #
    def _check_manual_override(self, current_pos: int) -> bool:
        """Check if manual override is active for this cover.

        Args:
            current_pos: Current cover position
            cover_attrs: Dictionary to store cover attributes

        Returns:
            True if override is active (should skip), False otherwise
        """

        # Check if we're still at the last known position
        last_history_entry = self._cover_pos_history_mgr.get_latest_entry(self.entity_id)
        if last_history_entry is None or current_pos == last_history_entry.position:
            return False

        # Beware of system time changes
        time_now = datetime.now(timezone.utc)
        if time_now <= last_history_entry.timestamp:
            return False

        # Are we past the override duration?
        time_delta = (time_now - last_history_entry.timestamp).total_seconds()
        if time_delta >= self.resolved.manual_override_duration:
            return False

        # Manual override still active
        time_remaining = self.resolved.manual_override_duration - time_delta
        message = f"Manual override detected (position changed externally), skipping this cover for another {time_remaining:.0f} s"
        self._log_cover_msg(message, const.LogSeverity.INFO)
        return True

    #
    # _calculate_sun_hitting
    #
    def _calculate_sun_hitting(self, sun_azimuth: float, sun_elevation: float, cover_azimuth: float) -> tuple[bool, float]:
        """Calculate if sun is hitting the window.

        Args:
            sun_azimuth: Current sun azimuth
            sun_elevation: Current sun elevation
            cover_azimuth: Cover azimuth (direction)

        Returns:
            Tuple of (is_sun_hitting, azimuth_difference)
        """

        sun_azimuth_difference = self._calculate_angle_difference(sun_azimuth, cover_azimuth)
        if sun_elevation >= self.resolved.sun_elevation_threshold:
            sun_hitting = sun_azimuth_difference < self.resolved.sun_azimuth_tolerance
        else:
            sun_hitting = False

        return sun_hitting, sun_azimuth_difference

    #
    # _calculate_angle_difference
    #
    @staticmethod
    def _calculate_angle_difference(angle1: float, angle2: float) -> float:
        """Calculate the smallest difference between two angles.

        Args:
            angle1: First angle in degrees
            angle2: Second angle in degrees

        Returns:
            Smallest angle difference in degrees (0-180)
        """

        diff = abs(angle1 - angle2)
        if diff > 180:
            diff = 360 - diff
        return diff

    #
    # _calculate_desired_position
    #
    def _calculate_desired_position(self, sensor_data: SensorData, sun_hitting: bool) -> tuple[int, CoverMovementReason]:
        """Calculate desired cover position based on conditions.

        Args:
            sensor_data: Current sensor data
            sun_hitting: Whether sun is hitting the window

        Returns:
            Tuple of (desired_position, verb_translation_key, reason_translation_key)
        """

        # Check if cover should close after sunset (takes priority over normal automation)
        if sensor_data.should_close_for_sunset and self.entity_id in self.resolved.close_covers_after_sunset_cover_list:
            desired_pos = const.COVER_POS_FULLY_CLOSED
            desired_pos_friendly_name = "night privacy state (closed)"
            movement_reason = CoverMovementReason.CLOSING_AFTER_SUNSET
        elif sensor_data.temp_hot and sensor_data.weather_sunny and sun_hitting:
            # Heat protection mode - close the cover
            max_closure_limit = self._get_cover_closure_limit(get_max=True)
            desired_pos = max(const.COVER_POS_FULLY_CLOSED, max_closure_limit)
            desired_pos_friendly_name = "heat protection state (closed)"
            movement_reason = CoverMovementReason.CLOSING_HEAT_PROTECTION
        else:
            # "Let light in" mode - open the cover
            min_closure_limit = self._get_cover_closure_limit(get_max=False)
            desired_pos = min(const.COVER_POS_FULLY_OPEN, min_closure_limit)
            desired_pos_friendly_name = "normal state (open)"
            movement_reason = CoverMovementReason.OPENING_LET_LIGHT_IN

        self._log_cover_msg(f"Desired position: {desired_pos}%, {desired_pos_friendly_name}", const.LogSeverity.INFO)

        return desired_pos, movement_reason

    #
    # _get_cover_closure_limit
    #
    def _get_cover_closure_limit(self, get_max: bool) -> int:
        """Get the closure limit for this cover.

        Checks for per-cover override first, then falls back to global config.

        Args:
            get_max: If True, get max closure limit (for closing), otherwise min (for opening)

        Returns:
            Closure limit position (0-100)
        """

        if get_max:
            per_cover_key = f"{self.entity_id}_{const.COVER_SFX_MAX_CLOSURE}"
            global_default = self.resolved.covers_max_closure
        else:
            per_cover_key = f"{self.entity_id}_{const.COVER_SFX_MIN_CLOSURE}"
            global_default = self.resolved.covers_min_closure

        # Check for per-cover override, otherwise use global config
        limit = to_int_or_none(self.config.get(per_cover_key))
        return limit if limit is not None else global_default

    #
    # _move_cover_if_needed
    #
    async def _move_cover_if_needed(
        self, current_pos: int, desired_pos: int, features: int, movement_reason: CoverMovementReason
    ) -> tuple[bool, int | None, str]:
        """Move cover if position change is significant enough.

        Args:
            current_pos: Current cover position
            desired_pos: Desired cover position
            features: Cover supported features
            verb_key: Translation key for logbook verb
            reason_key: Translation key for logbook reason
            cover_attrs: Dictionary to store cover attributes

        Returns:
            Tuple of (movement_needed, actual_pos, message)
        """

        # Determine if cover movement is necessary
        if desired_pos == current_pos:
            return False, None, "No movement needed"

        if abs(desired_pos - current_pos) < self.resolved.covers_min_position_delta:
            return False, None, "Skipped minor adjustment"

        # Movement needed
        try:
            # Move the cover
            actual_pos = await self._ha_interface.set_cover_position(self.entity_id, desired_pos, features)
            const.LOGGER.debug(f"[{self.entity_id}] Actual position: {actual_pos}%")

            # Add the new position to the history
            self._cover_pos_history_mgr.add(self.entity_id, actual_pos, cover_moved=True)

            if movement_reason == CoverMovementReason.CLOSING_HEAT_PROTECTION:
                verb_key = const.TRANSL_LOGBOOK_VERB_CLOSING
                reason_key = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION
            elif movement_reason == CoverMovementReason.OPENING_LET_LIGHT_IN:
                verb_key = const.TRANSL_LOGBOOK_VERB_OPENING
                reason_key = const.TRANSL_LOGBOOK_REASON_LET_LIGHT_IN
            elif movement_reason == CoverMovementReason.CLOSING_AFTER_SUNSET:
                verb_key = const.TRANSL_LOGBOOK_VERB_CLOSING
                reason_key = const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET
            else:
                # Type checker will fail if a new enum value is added but not handled
                assert_never(movement_reason)

            # Add detailed logbook entry
            await self._ha_interface.add_logbook_entry(
                verb_key=verb_key, entity_id=self.entity_id, reason_key=reason_key, target_pos=actual_pos
            )

            return True, actual_pos, "Moved cover"

        except Exception as err:
            # Log the error but continue with other covers
            const.LOGGER.error(f"[{self.entity_id}] Failed to control cover: {err}")
            return False, None, f"Error: {err}"

    #
    # _log_cover_msg
    #
    def _log_cover_msg(self, message: str, severity: const.LogSeverity) -> None:
        """Log a message for one cover.

        Args:
            entity_id: Cover entity ID
            message: String to log
            severity: Log severity level
        """

        # Prefix message with entity ID
        message = f"[{self.entity_id}] {message}"

        # Log the message
        if severity == const.LogSeverity.DEBUG:
            const.LOGGER.debug(message)
        elif severity == const.LogSeverity.INFO:
            const.LOGGER.info(message)
        elif severity == const.LogSeverity.WARNING:
            const.LOGGER.warning(message)
        else:
            const.LOGGER.error(message)
