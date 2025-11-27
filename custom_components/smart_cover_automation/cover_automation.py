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


@dataclass
class CoverState:
    """Type-safe container for cover automation state.

    Note: Lock state and position history are managed separately
    as CoverAutomation member variables and added during to_dict().
    """

    # Cover configuration
    cover_azimuth: float | None = None

    # Cover physical state
    state: str | None = None
    supported_features: int | None = None
    pos_current: int | None = None

    # Automation targets
    pos_target_desired: int | None = None
    pos_target_final: int | None = None

    # Sun calculations
    sun_hitting: bool | None = None
    sun_azimuth_diff: float | None = None

    # Protection states
    lockout_protection: bool | None = None


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
    # _cover_state_to_dict
    #
    def _cover_state_to_dict(self, cover_state: CoverState) -> dict[str, Any]:
        """Convert CoverState to dictionary, adding data from member variables.

        Only includes fields that have been set (not None) to maintain backward compatibility.

        Args:
            cover_state: The cover state object

        Returns:
            Dictionary with all cover attributes for coordinator.data storage
        """

        result: dict[str, Any] = {}

        # Add fields from CoverState (only if they have values)
        if cover_state.cover_azimuth is not None:
            result[const.COVER_ATTR_COVER_AZIMUTH] = cover_state.cover_azimuth
        if cover_state.state is not None:
            result[const.COVER_ATTR_STATE] = cover_state.state
        if cover_state.supported_features is not None:
            result[const.COVER_ATTR_SUPPORTED_FEATURES] = cover_state.supported_features
        if cover_state.pos_current is not None:
            result[const.COVER_ATTR_POS_CURRENT] = cover_state.pos_current
        if cover_state.pos_target_desired is not None:
            result[const.COVER_ATTR_POS_TARGET_DESIRED] = cover_state.pos_target_desired
        if cover_state.pos_target_final is not None:
            result[const.COVER_ATTR_POS_TARGET_FINAL] = cover_state.pos_target_final
        if cover_state.sun_hitting is not None:
            result[const.COVER_ATTR_SUN_HITTING] = cover_state.sun_hitting
        if cover_state.sun_azimuth_diff is not None:
            result[const.COVER_ATTR_SUN_AZIMUTH_DIFF] = cover_state.sun_azimuth_diff
        if cover_state.lockout_protection is not None:
            result[const.COVER_ATTR_LOCKOUT_PROTECTION] = cover_state.lockout_protection

        # TODO: remove
        # Always add lock mode and lock active status from resolved config
        result[const.COVER_ATTR_LOCK_MODE] = self.resolved.lock_mode
        result[const.COVER_ATTR_LOCK_ACTIVE] = self.resolved.lock_mode != const.LockMode.UNLOCKED

        # Add position history from position history manager (only if there are entries)
        position_entries = self._cover_pos_history_mgr.get_entries(self.entity_id)
        position_list = [entry.position for entry in position_entries]
        if position_list or cover_state.pos_current is not None:
            # Include position history if there are entries OR if we have a current position
            # (which means we successfully processed far enough to know the current position)
            result[const.COVER_ATTR_POS_HISTORY] = position_list

        return result

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

        cover_state = CoverState()

        # Get cover azimuth
        cover_azimuth = self._get_cover_azimuth()
        if cover_azimuth is None:
            return self._cover_state_to_dict(cover_state)
        else:
            cover_state.cover_azimuth = cover_azimuth

        # Validate current cover state
        if not self._validate_cover_state(state):
            return self._cover_state_to_dict(cover_state)
        else:
            # At this point, we know state is not None due to validation (type narrowing for type checkers)
            assert state is not None
            cover_state.state = state.state

        # Check if cover is moving
        if self._is_cover_moving(state):
            return self._cover_state_to_dict(cover_state)

        # Get cover features
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        cover_state.supported_features = features

        # Get cover position
        success, current_pos = self._get_cover_position(state, features)
        if not success:
            return self._cover_state_to_dict(cover_state)
        else:
            cover_state.pos_current = current_pos

        # Handle lock modes before normal automation logic
        locked = await self._process_lock_mode(cover_state, current_pos, features)
        if locked:
            return self._cover_state_to_dict(cover_state)

        # Check for manual override
        if self._check_manual_override(current_pos):
            return self._cover_state_to_dict(cover_state)

        # Calculate sun hitting
        sun_hitting, sun_azimuth_difference = self._calculate_sun_hitting(sensor_data.sun_azimuth, sensor_data.sun_elevation, cover_azimuth)
        cover_state.sun_hitting = sun_hitting
        cover_state.sun_azimuth_diff = round(sun_azimuth_difference, 1)

        # Calculate desired position (lockout protection and nighttime block are checked inside _calculate_desired_position)
        desired_pos, movement_reason, lockout_protection = self._calculate_desired_position(sensor_data, sun_hitting, current_pos)
        cover_state.pos_target_desired = desired_pos
        cover_state.lockout_protection = lockout_protection

        # Move cover if needed (skip if movement_reason is None, e.g., nighttime block active)
        if movement_reason is None:
            # No movement - nighttime block or other condition preventing movement
            self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            movement_needed = False
            message = "No movement (blocked by nighttime or other condition)"
        else:
            movement_needed, actual_pos, message = await self._move_cover_if_needed(current_pos, desired_pos, features, movement_reason)
            if not movement_needed:
                # No movement - just add the current position to the history
                self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            else:
                # Movement occurred
                cover_state.pos_target_final = actual_pos

        # Log per-cover attributes
        result = self._cover_state_to_dict(cover_state)
        const.LOGGER.debug(f"[{self.entity_id}] Cover result: {message}. Cover data: {str(result)}")

        return result

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
    # _is_lockout_protection_active
    #
    def _is_lockout_protection_active(self, movement_reason: CoverMovementReason) -> bool:
        """Check if lockout protection should be enforced for this cover.

        Lockout protection prevents cover closing when associated window sensors indicate
        that a window is open. This applies to both heat protection and sunset closing.

        Args:
            movement_reason: The reason for the potential cover movement

        Returns:
            True if lockout is active (should prevent closing), False otherwise
        """

        # Only apply to closing operations
        if movement_reason not in (CoverMovementReason.CLOSING_HEAT_PROTECTION, CoverMovementReason.CLOSING_AFTER_SUNSET):
            return False

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
        if open_sensors:
            self._log_cover_msg("Lockout protection active, preventing closing", const.LogSeverity.INFO)
            return True

        return False

    #
    # _is_nighttime_block_active
    #
    def _is_nighttime_block_active(self) -> bool:
        """Check if nighttime block opening should prevent cover opening.

        The nighttime block feature prevents automatic cover opening during nighttime
        (when the sun is below the horizon). This does NOT prevent closing operations.

        Returns:
            True if nighttime block is active and should prevent opening, False otherwise
        """

        # Check if feature is enabled
        if not self.resolved.nighttime_block_opening:
            return False

        # Check if sun is below horizon
        sun_state = self._ha_interface.get_sun_state()
        if sun_state == const.HA_SUN_STATE_BELOW_HORIZON:
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
    def _calculate_desired_position(
        self, sensor_data: SensorData, sun_hitting: bool, current_pos: int
    ) -> tuple[int, CoverMovementReason | None, bool]:
        """Calculate the desired cover position based on sensor data.

        Returns a tuple of (desired_position, movement_reason, lockout_protection_active).
        """

        lockout_protection_active = False

        if sensor_data.should_close_for_sunset and self.entity_id in self.resolved.close_covers_after_sunset_cover_list:
            # Evening closure mode - check lockout protection first
            if self._is_lockout_protection_active(CoverMovementReason.CLOSING_AFTER_SUNSET):
                # Lockout protection active - keep current position (prevent closing)
                lockout_protection_active = True
                desired_pos = current_pos
                desired_pos_friendly_name = "unchanged (lockout protection active)"
                movement_reason = None  # No movement when lockout active
            else:
                # No lockout - close the cover
                max_closure_limit = self._get_cover_closure_limit(get_max=True)
                desired_pos = max(const.COVER_POS_FULLY_CLOSED, max_closure_limit)
                desired_pos_friendly_name = "evening closure state (closed)"
                movement_reason = CoverMovementReason.CLOSING_AFTER_SUNSET
        elif sensor_data.temp_hot and sensor_data.weather_sunny and sun_hitting:
            # Heat protection mode - check lockout protection first
            if self._is_lockout_protection_active(CoverMovementReason.CLOSING_HEAT_PROTECTION):
                # Lockout protection active - keep current position (prevent closing)
                lockout_protection_active = True
                desired_pos = current_pos
                desired_pos_friendly_name = "unchanged (lockout protection active)"
                movement_reason = None  # No movement when lockout active
            else:
                # No lockout - close the cover
                max_closure_limit = self._get_cover_closure_limit(get_max=True)
                desired_pos = max(const.COVER_POS_FULLY_CLOSED, max_closure_limit)
                desired_pos_friendly_name = "heat protection state (closed)"
                movement_reason = CoverMovementReason.CLOSING_HEAT_PROTECTION
        else:
            # Let light in mode - check if nighttime block is active
            if self._is_nighttime_block_active():
                # Nighttime block active - keep current position (no movement)
                desired_pos = current_pos
                desired_pos_friendly_name = "unchanged (nighttime block active)"
                movement_reason = None  # No movement reason when nighttime block active
            else:
                # No nighttime block - open the cover
                min_closure_limit = self._get_cover_closure_limit(get_max=False)
                desired_pos = min(const.COVER_POS_FULLY_OPEN, min_closure_limit)
                desired_pos_friendly_name = "normal state (open)"
                movement_reason = CoverMovementReason.OPENING_LET_LIGHT_IN

        self._log_cover_msg(
            f"Current position: {current_pos}%, desired position: {desired_pos}%, {desired_pos_friendly_name}", const.LogSeverity.INFO
        )

        return desired_pos, movement_reason, lockout_protection_active

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
    # _process_lock_mode
    #
    async def _process_lock_mode(self, cover_state: CoverState, current_pos: int, features: int) -> bool:
        """Process lock modes.

        This method enforces the lock mode by:
        1. UNLOCKED: No action, normal automation
        2. HOLD_POSITION: Do nothing, skip automation
        3. FORCE_OPEN: Ensure cover is at 100%, move if not
        4. FORCE_CLOSE: Ensure cover is at 0%, move if not

        Args:
            cover_state: Cover state object to populate
            current_pos: Current cover position
            features: Cover supported features

        Returns:
            True if lock mode active (automation should be skipped), False otherwise
        """

        if self.resolved.lock_mode == const.LockMode.UNLOCKED:
            return False

        if self.resolved.lock_mode == const.LockMode.HOLD_POSITION:
            # Just block all automation
            self._log_cover_msg(f"Lock active ({self.resolved.lock_mode}), skipping automation", const.LogSeverity.INFO)
            self._set_lock_attrs(cover_state, desired_pos=current_pos, target_pos=current_pos, cover_moved=False)

        elif self.resolved.lock_mode == const.LockMode.FORCE_OPEN:
            # Ensure cover is fully open (100%)
            await self._enforce_locked_position(
                cover_state, current_pos=current_pos, target_pos=const.COVER_POS_FULLY_OPEN, features=features
            )

        elif self.resolved.lock_mode == const.LockMode.FORCE_CLOSE:
            # Ensure cover is fully closed (0%)
            await self._enforce_locked_position(
                cover_state, current_pos=current_pos, target_pos=const.COVER_POS_FULLY_CLOSED, features=features
            )

        else:
            # Have the type checker fail if a new lock mode is added but not handled here
            assert_never(self.resolved.lock_mode)

        return True

    #
    # _set_lock_attrs
    #
    def _set_lock_attrs(self, cover_state: CoverState, desired_pos: int, target_pos: int, cover_moved: bool) -> None:
        """Set lock-related attributes.

        Args:
            cover_state: Cover state object to populate
            desired_pos: Desired position
            target_pos: Target position
            cover_moved: Whether the cover moved
        """

        cover_state.pos_target_desired = desired_pos
        cover_state.pos_target_final = target_pos
        self._cover_pos_history_mgr.add(self.entity_id, new_position=target_pos, cover_moved=cover_moved)

    #
    # _enforce_locked_position
    #
    async def _enforce_locked_position(self, cover_state: CoverState, current_pos: int, target_pos: int, features: int) -> None:
        """Enforce a locked position (FORCE_OPEN or FORCE_CLOSE).

        Args:
            cover_state: Cover state object to populate
            current_pos: Current cover position
            target_pos: Target position to enforce
            features: Cover supported features
        """

        if current_pos == target_pos:
            cover_moved = False
            move_msg = "already at target position"
            new_pos = current_pos
        else:
            # Move the cover to the target position
            cover_moved = True
            move_msg = "moving to target position"
            new_pos = await self._ha_interface.set_cover_position(self.entity_id, target_pos, features)

        # Log and store position
        self._log_cover_msg(f"Lock active ({self.resolved.lock_mode}), {move_msg} ({target_pos}%)", const.LogSeverity.INFO)
        self._set_lock_attrs(cover_state, desired_pos=new_pos, target_pos=new_pos, cover_moved=cover_moved)

    #
    # _log_cover_msg
    #
    def _log_cover_msg(self, message: str, severity: const.LogSeverity) -> None:
        """Log a message for one cover.

        Args:
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
