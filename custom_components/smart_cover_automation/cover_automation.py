"""Cover automation logic for individual covers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, assert_never

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_CURRENT_TILT_POSITION, CoverEntityFeature
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
from .log import Log
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

    Position history is managed by CoverPositionHistoryManager.
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

    # Tilt state
    tilt_current: int | None = None
    tilt_target: int | None = None

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
        logger: Log,
    ) -> None:
        """Initialize cover automation.

        Args:
            entity_id: Cover entity ID
            resolved: Resolved configuration settings
            config: Raw configuration dictionary
            cover_pos_history_mgr: Cover position history manager
            ha_interface: Home Assistant interface for API interactions
            logger: Instance-specific logger with entry_id prefix
        """

        self.entity_id = entity_id
        self.resolved = resolved
        self.config = config
        self._cover_pos_history_mgr = cover_pos_history_mgr
        self._ha_interface = ha_interface
        self._logger = logger

        # Tilt support: cached flag (set on first process() call)
        self._cover_supports_tilt: bool | None = None

    #
    # process
    #
    async def process(self, state: State | None, sensor_data: SensorData) -> CoverState:
        """Process automation for this cover.

        Args:
            state: Current state of the cover
            sensor_data: Gathered sensor data

        Returns:
            CoverState object with automation results
        """

        cover_state = CoverState()

        # Get cover azimuth
        cover_azimuth = self._get_cover_azimuth()
        if cover_azimuth is None:
            return cover_state
        else:
            cover_state.cover_azimuth = cover_azimuth

        # Validate current cover state
        if not self._validate_cover_state(state):
            return cover_state
        else:
            # At this point, we know state is not None due to validation (type narrowing for type checkers)
            assert state is not None
            cover_state.state = state.state

        # Check if cover is moving
        if self._is_cover_moving(state):
            return cover_state

        # Get cover features
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        cover_state.supported_features = features

        # Cache tilt support flag on first call
        if self._cover_supports_tilt is None:
            self._cover_supports_tilt = bool(int(features) & CoverEntityFeature.SET_TILT_POSITION)

        # Read current tilt position (for Manual mode tracking and delta checks)
        if self._cover_supports_tilt:
            cover_state.tilt_current = to_int_or_none(state.attributes.get(ATTR_CURRENT_TILT_POSITION))

        # Get cover position
        success, current_pos = self._get_cover_position(state, features)
        if not success:
            return cover_state
        else:
            cover_state.pos_current = current_pos

        # Handle lock modes before normal automation logic
        locked = await self._process_lock_mode(cover_state, current_pos, features)
        if locked:
            return cover_state

        # Check for manual override
        if self._check_manual_override(current_pos):
            return cover_state

        # Calculate sun hitting
        sun_hitting, sun_azimuth_difference = self._calculate_sun_hitting(sensor_data.sun_azimuth, sensor_data.sun_elevation, cover_azimuth)
        cover_state.sun_hitting = sun_hitting
        cover_state.sun_azimuth_diff = round(sun_azimuth_difference, 1)

        # Calculate desired position (lockout protection and nighttime opening block are checked inside _calculate_desired_position)
        desired_pos, movement_reason, lockout_protection = self._calculate_desired_position(sensor_data, sun_hitting, current_pos)
        cover_state.pos_target_desired = desired_pos
        cover_state.lockout_protection = lockout_protection

        # Move cover if needed (skip if movement_reason is None, e.g., nighttime block active)
        if movement_reason is None:
            # No movement - nighttime opening block or other condition preventing movement
            self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            cover_moved = False
            message = "No movement (blocked by nighttime or other condition)"
        else:
            cover_moved, actual_pos, message = await self._move_cover_if_needed(current_pos, desired_pos, features, movement_reason)
            if not cover_moved:
                # No movement - just add the current position to the history
                self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            else:
                # Movement occurred
                cover_state.pos_target_final = actual_pos

        # Apply tilt after position handling — skip only when the nighttime opening block is
        # active (cover opening suppressed at night).  Other reasons for no position
        # change (e.g. lockout protection) should still allow tilt updates.
        if not self._is_nighttime_opening_block_active():
            await self._apply_tilt(cover_state, sensor_data, features, movement_reason, cover_moved)

        # Log per-cover state
        self._logger.debug(f"[{self.entity_id}] Cover result: {message}. Cover state: {cover_state}")

        return cover_state

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
        that a window is open. This applies to both heat protection and evening closure.

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
    # _is_nighttime_opening_block_active
    #
    def _is_nighttime_opening_block_active(self) -> bool:
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
            if self._is_nighttime_opening_block_active():
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
            self._logger.debug(f"[{self.entity_id}] Actual position: {actual_pos}%")

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
            self._logger.error(f"[{self.entity_id}] Failed to control cover: {err}")
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
            # Just block all automation (including tilt)
            self._log_cover_msg(f"Lock active ({self.resolved.lock_mode}), skipping automation", const.LogSeverity.INFO)
            self._set_lock_attrs(cover_state, desired_pos=current_pos, target_pos=current_pos, cover_moved=False)

        elif self.resolved.lock_mode == const.LockMode.FORCE_OPEN:
            # Ensure cover is fully open (100%) and tilt is fully open (100%)
            await self._enforce_locked_position(
                cover_state, current_pos=current_pos, target_pos=const.COVER_POS_FULLY_OPEN, features=features
            )
            if self._cover_supports_tilt:
                try:
                    await self._ha_interface.set_cover_tilt_position(self.entity_id, const.COVER_POS_FULLY_OPEN, features)
                    cover_state.tilt_target = const.COVER_POS_FULLY_OPEN
                except Exception as err:
                    self._logger.error(f"[{self.entity_id}] Failed to set lock tilt: {err}")

        elif self.resolved.lock_mode == const.LockMode.FORCE_CLOSE:
            # Ensure cover is fully closed (0%) and tilt is fully closed (0%)
            await self._enforce_locked_position(
                cover_state, current_pos=current_pos, target_pos=const.COVER_POS_FULLY_CLOSED, features=features
            )
            if self._cover_supports_tilt:
                try:
                    await self._ha_interface.set_cover_tilt_position(self.entity_id, const.COVER_POS_FULLY_CLOSED, features)
                    cover_state.tilt_target = const.COVER_POS_FULLY_CLOSED
                except Exception as err:
                    self._logger.error(f"[{self.entity_id}] Failed to set lock tilt: {err}")

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
    # _get_effective_tilt_mode
    #
    def _get_effective_tilt_mode(self, is_night: bool) -> str | None:
        """Get the effective tilt mode for this cover.

        Checks per-cover override first, falls back to global setting.
        Returns None if the cover doesn't support tilt.

        Args:
            is_night: True for night/evening closure mode, False for daytime

        Returns:
            Tilt mode string or None if tilt not supported
        """

        if self._cover_supports_tilt is False:
            return None

        # Determine suffix and global default based on day/night
        if is_night:
            suffix = const.COVER_SFX_TILT_MODE_NIGHT
            global_default = self.resolved.tilt_mode_night
        else:
            suffix = const.COVER_SFX_TILT_MODE_DAY
            global_default = self.resolved.tilt_mode_day

        # Check for per-cover override
        per_cover_key = f"{self.entity_id}_{suffix}"
        per_cover_value = self.config.get(per_cover_key)
        if per_cover_value is not None:
            return str(per_cover_value)

        return global_default

    #
    # _calculate_auto_tilt
    #
    @staticmethod
    def _calculate_auto_tilt(
        sun_elevation: float,
        sun_azimuth_diff: float,
        slat_overlap_ratio: float,
    ) -> int:
        """Calculate optimal tilt to block direct sunlight while maximizing daylight.

        Uses the profile-angle / slat-cutoff formula with a configurable slat overlap
        ratio (d/L). The default of 0.9 works for most venetian blinds without
        requiring the user to measure their slats.

        Args:
            sun_elevation: Sun elevation in degrees (0-90).
            sun_azimuth_diff: Absolute azimuth difference between sun and cover (0-180°).
            slat_overlap_ratio: Ratio of slat spacing to slat width (d/L, typically 0.5-1.0).

        Returns:
            Tilt position 0-100 (0 = closed/vertical, 100 = open/horizontal).
        """

        if sun_elevation <= 0:
            return 0  # Sun at/below horizon → fully closed

        # Step 1: Profile angle (ω) — vertical sun angle projected onto facade-normal plane
        alt_rad = math.radians(sun_elevation)
        hsa_rad = math.radians(sun_azimuth_diff)
        cos_hsa = math.cos(hsa_rad)

        if abs(cos_hsa) < 1e-10:
            # Sun nearly parallel to facade → profile angle approaches 90°
            omega_rad = math.pi / 2
        else:
            omega_rad = math.atan(math.tan(alt_rad) / cos_hsa)

        # Step 2: Slat cut-off angle (θ) from sin(θ + ω) = (d/L) · cos(ω)
        cos_omega = math.cos(omega_rad)
        ratio = slat_overlap_ratio * cos_omega

        if ratio > 1.0:
            # Geometry impossible — fully close
            theta_deg = 90.0
        elif ratio < -1.0:
            theta_deg = 0.0
        else:
            theta_rad = math.asin(ratio) - omega_rad
            theta_deg = math.degrees(theta_rad)

        # Step 3: Clamp and convert to HA tilt percentage
        theta_deg = max(0.0, min(90.0, theta_deg))
        tilt_percent = 100.0 * (1.0 - theta_deg / 90.0)
        return max(0, min(100, round(tilt_percent)))

    #
    # _apply_tilt
    #
    async def _apply_tilt(
        self,
        cover_state: CoverState,
        sensor_data: SensorData,
        features: int,
        movement_reason: CoverMovementReason | None,
        cover_moved: bool,
    ) -> None:
        """Apply tilt angle to the cover based on tilt mode and context.

        Determines the appropriate tilt mode (day or night), calculates the target
        tilt position, and sends the tilt command if the change exceeds the minimum
        delta threshold.

        Args:
            cover_state: Cover state object to update with tilt info
            sensor_data: Current sensor data
            features: Cover's supported features bitmask
            movement_reason: The reason for cover movement (or None if no movement)
            cover_moved: Whether the cover position was changed this cycle
        """

        # Determine day/night context
        is_night = movement_reason == CoverMovementReason.CLOSING_AFTER_SUNSET
        tilt_mode = self._get_effective_tilt_mode(is_night)

        if tilt_mode is None:
            return  # Cover doesn't support tilt

        # Determine target tilt based on mode
        target_tilt: int | None = None

        if tilt_mode == const.TiltMode.OPEN:
            target_tilt = const.COVER_POS_FULLY_OPEN  # 100
        elif tilt_mode == const.TiltMode.CLOSED:
            target_tilt = const.COVER_POS_FULLY_CLOSED  # 0
        elif tilt_mode == const.TiltMode.MANUAL:
            # Restore the tilt the cover had before automation moved it.
            # cover_state.tilt_current was read from the HA state *before* the
            # position change, so it reflects the user's (or previous) setting.
            target_tilt = cover_state.tilt_current
            if target_tilt is None:
                return  # No tilt info available
        elif tilt_mode == const.TiltMode.AUTO:
            if cover_state.sun_hitting and cover_state.sun_azimuth_diff is not None:
                target_tilt = self._calculate_auto_tilt(
                    sensor_data.sun_elevation,
                    cover_state.sun_azimuth_diff,
                    self.resolved.tilt_slat_overlap_ratio,
                )
            else:
                # Sun not hitting — open tilt fully to let in diffuse daylight
                target_tilt = const.COVER_POS_FULLY_OPEN
        elif tilt_mode == const.TiltMode.SET_VALUE:
            target_tilt = self.resolved.tilt_set_value_night if is_night else self.resolved.tilt_set_value_day

        if target_tilt is None:
            return

        cover_state.tilt_target = target_tilt

        # Check minimum change delta (skip if cover was just moved — always apply tilt then)
        current_tilt = cover_state.tilt_current
        if not cover_moved and current_tilt is not None:
            if abs(target_tilt - current_tilt) < self.resolved.tilt_min_change_delta:
                self._log_cover_msg(
                    f"Tilt change too small ({current_tilt}% → {target_tilt}%), skipping",
                    const.LogSeverity.DEBUG,
                )
                return

        # Send tilt command
        try:
            actual_tilt = await self._ha_interface.set_cover_tilt_position(self.entity_id, target_tilt, features)
            cover_state.tilt_target = actual_tilt
            self._log_cover_msg(
                f"Tilt set to {actual_tilt}% (mode: {tilt_mode})",
                const.LogSeverity.INFO,
            )
        except Exception as err:
            self._logger.error(f"[{self.entity_id}] Failed to set tilt: {err}")

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
            self._logger.debug(message)
        elif severity == const.LogSeverity.INFO:
            self._logger.info(message)
        elif severity == const.LogSeverity.WARNING:
            self._logger.warning(message)
        else:
            self._logger.error(message)
