"""Cover automation logic for individual covers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from .cover_position_history import CoverPositionHistoryManager, PositionEntry
from .log import Log
from .util import to_float_or_none, to_int_or_none

if TYPE_CHECKING:
    from homeassistant.core import State


COVER_RESULT_NO_MOVEMENT = "no movement"


class CoverMovementReason(Enum):
    """Encapsulates cover movement and reason."""

    CLOSING_HEAT_PROTECTION = "closing_heat_protection"
    PREPARING_REOPEN_AFTER_HEAT_PROTECTION = "preparing_reopen_after_heat_protection"
    OPENING_LET_LIGHT_IN = "opening_let_light_in"
    OPENING_AFTER_HEAT_PROTECTION = "opening_after_heat_protection"
    OPENING_AFTER_MANUAL_OVERRIDE = "opening_after_manual_override"
    OPENING_AFTER_EVENING_CLOSURE = "opening_after_evening_closure"
    CLOSING_AFTER_SUNSET = "closing_after_sunset"
    CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE = "closing_keep_closed_after_evening_closure"


@dataclass(slots=True)
class SensorData:
    """Encapsulates sensor data gathered for an automation run."""

    sun_azimuth: float
    sun_elevation: float
    temp_max: float | None
    temp_min: float | None
    temp_hot: bool | None
    weather_condition: str | None
    weather_sunny: bool | None
    evening_closure: bool
    post_evening_closure: bool
    has_valid_external_evening_closure_time: bool = True
    has_valid_external_morning_opening_time: bool = True


@dataclass(slots=True)
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

        manual_override_just_expired = False

        # Check for manual override
        was_manual_override_blocking = self._cover_pos_history_mgr.was_manual_override_blocking(self.entity_id)
        manual_override_remaining = self._get_manual_override_remaining(current_pos)
        if manual_override_remaining is not None:
            self._cover_pos_history_mgr.clear_closed_by_automation(self.entity_id)
            self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
            if self._should_ignore_manual_override(sensor_data):
                self._cover_pos_history_mgr.clear_manual_override_blocked(self.entity_id)
                message = (
                    f"Ignoring manual override during evening-closure trigger; {manual_override_remaining:.0f} s would otherwise remain"
                )
                self._log_cover_msg(message, const.LogSeverity.INFO)
            else:
                self._cover_pos_history_mgr.mark_manual_override_blocked(self.entity_id)
                message = (
                    "Manual override detected (position changed externally), "
                    f"skipping this cover for another {manual_override_remaining:.0f} s"
                )
                self._log_cover_msg(message, const.LogSeverity.INFO)
                return cover_state
        elif was_manual_override_blocking:
            manual_override_just_expired = True
            self._cover_pos_history_mgr.clear_manual_override_blocked(self.entity_id)

        # Calculate sun hitting
        sun_hitting, sun_azimuth_difference = self._calculate_sun_hitting(sensor_data.sun_azimuth, sensor_data.sun_elevation, cover_azimuth)
        cover_state.sun_hitting = sun_hitting
        cover_state.sun_azimuth_diff = round(sun_azimuth_difference, 1)

        if self._has_missing_external_evening_closure_time(sensor_data):
            self._log_cover_msg(
                "External evening closure mode active but no valid time is set, skipping evening closure",
                const.LogSeverity.DEBUG,
            )

        if self._has_missing_external_morning_opening_time(sensor_data):
            self._log_cover_msg(
                "External morning opening mode active but no valid time is set, skipping automatic reopening",
                const.LogSeverity.DEBUG,
            )

        # Calculate desired position (lockout protection and opening block after evening closure are checked inside _calculate_desired_position)
        desired_pos, movement_reason, lockout_protection = self._calculate_desired_position(
            sensor_data,
            sun_hitting,
            current_pos,
            manual_override_just_expired=manual_override_just_expired,
        )
        cover_state.pos_target_desired = desired_pos
        cover_state.lockout_protection = lockout_protection

        # Move cover if needed (skip if movement_reason is None, e.g., opening block after evening closure active)
        if movement_reason is None:
            # No movement - the reason is already covered by the INFO log above.
            self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            cover_moved = False
            message = COVER_RESULT_NO_MOVEMENT
        else:
            cover_moved, actual_pos, message = await self._move_cover_if_needed(current_pos, desired_pos, features, movement_reason)
            if not cover_moved:
                # No movement - just add the current position to the history
                self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            else:
                # Movement occurred
                cover_state.pos_target_final = actual_pos

        # Apply tilt only when an automation movement context is active.
        if movement_reason is not None:
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
        if movement_reason not in (
            CoverMovementReason.CLOSING_HEAT_PROTECTION,
            CoverMovementReason.CLOSING_AFTER_SUNSET,
            CoverMovementReason.CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE,
        ):
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
    # _is_opening_block_after_evening_closure_active
    #
    def _is_opening_block_after_evening_closure_active(self, sensor_data: SensorData) -> bool:
        """Check if opening block after evening closure should prevent cover opening.

        This prevents automatic cover opening once the evening closure time has
        passed. The block then remains active until the configured morning
        opening time is reached.

        Returns:
            True if block is active and should prevent opening, False otherwise
        """

        return sensor_data.post_evening_closure

    def _get_evening_closure_movement_reason(self, sensor_data: SensorData) -> CoverMovementReason | None:
        """Return the evening-closure movement reason for this cover and cycle.

        The result is limited to covers explicitly included in the evening
        closure list. The initial evening-closure trigger takes precedence over
        the overnight keep-closed period because it represents the more specific
        transition event.
        """

        if self.entity_id not in self.resolved.evening_closure_cover_list:
            return None

        if self._has_missing_external_evening_closure_time(sensor_data):
            return None

        if sensor_data.evening_closure:
            return CoverMovementReason.CLOSING_AFTER_SUNSET

        if self.resolved.evening_closure_keep_closed and sensor_data.post_evening_closure:
            return CoverMovementReason.CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE

        return None

    def _has_missing_external_evening_closure_time(self, sensor_data: SensorData) -> bool:
        """Return whether evening closure is externally controlled but has no valid time."""

        return (
            self.resolved.evening_closure_enabled
            and self.resolved.evening_closure_mode == const.EveningClosureMode.EXTERNAL
            and self.entity_id in self.resolved.evening_closure_cover_list
            and not sensor_data.has_valid_external_evening_closure_time
        )

    def _has_missing_external_morning_opening_time(self, sensor_data: SensorData) -> bool:
        """Return whether morning opening is externally controlled but has no valid time."""

        return (
            self.resolved.evening_closure_enabled
            and self.resolved.morning_opening_mode == const.MorningOpeningMode.EXTERNAL
            and self.entity_id in self.resolved.evening_closure_cover_list
            and not sensor_data.has_valid_external_morning_opening_time
        )

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

        time_remaining = self._get_manual_override_remaining(current_pos)
        if time_remaining is None:
            return False

        message = f"Manual override detected (position changed externally), skipping this cover for another {time_remaining:.0f} s"
        self._log_cover_msg(message, const.LogSeverity.INFO)
        return True

    #
    # _get_manual_override_remaining
    #
    def _get_manual_override_remaining(self, current_pos: int) -> float | None:
        """Get remaining manual override time for this cover.

        Args:
            current_pos: Current cover position

        Returns:
            Remaining override time in seconds, or None if manual override is inactive
        """

        # Check if we're still at the last known position
        last_history_entry = self._cover_pos_history_mgr.get_latest_entry(self.entity_id)
        if last_history_entry is None or current_pos == last_history_entry.position:
            return None

        time_now = datetime.now(timezone.utc)

        if self._is_expected_recent_automation_position_drift(current_pos, last_history_entry, time_now):
            return None

        # Beware of system time changes
        if time_now <= last_history_entry.timestamp:
            return None

        # Are we past the override duration?
        time_delta = (time_now - last_history_entry.timestamp).total_seconds()
        if time_delta >= self.resolved.manual_override_duration:
            return None

        return self.resolved.manual_override_duration - time_delta

    #
    # _is_expected_recent_automation_position_drift
    #
    def _is_expected_recent_automation_position_drift(
        self,
        current_pos: int,
        last_history_entry: PositionEntry,
        time_now: datetime,
    ) -> bool:
        """Check whether a small position drift is an expected automation settle effect.

        Args:
            current_pos: Current live cover position
            last_history_entry: Most recent recorded position history entry
            time_now: Current UTC time for expiry checks

        Returns:
            True if the position change should be ignored as recent automation settling
        """

        recent_automation_action = self._cover_pos_history_mgr.get_recent_automation_action(self.entity_id)
        if recent_automation_action is None:
            return False

        if time_now > recent_automation_action.expires_at:
            self._cover_pos_history_mgr.clear_recent_automation_action(self.entity_id)
            return False

        lower_bound = max(
            const.COVER_POS_FULLY_CLOSED,
            recent_automation_action.expected_position - recent_automation_action.allowed_position_drift,
        )
        upper_bound = min(
            const.COVER_POS_FULLY_OPEN,
            recent_automation_action.expected_position + recent_automation_action.allowed_position_drift,
        )

        if not lower_bound <= current_pos <= upper_bound:
            self._cover_pos_history_mgr.clear_recent_automation_action(self.entity_id)
            return False

        self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=True, timestamp=time_now)
        self._log_cover_msg(
            (f"Ignoring expected recent automation position drift ({last_history_entry.position}% -> {current_pos}%)"),
            const.LogSeverity.DEBUG,
        )
        return True

    #
    # _record_recent_automation_action
    #
    def _record_recent_automation_action(self, expected_position: int | None) -> None:
        """Record a short-lived tolerance window for recent automation settling.

        Args:
            expected_position: The position automation intended to leave the cover at
        """

        if expected_position is None:
            return

        expires_at = datetime.now(timezone.utc) + (const.UPDATE_INTERVAL * const.COVER_AUTOMATION_SETTLE_CYCLES)
        self._cover_pos_history_mgr.set_recent_automation_action(
            self.entity_id,
            expected_position=expected_position,
            allowed_position_drift=self.resolved.covers_min_position_delta,
            expires_at=expires_at,
        )

    #
    # _should_ignore_manual_override
    #
    def _should_ignore_manual_override(self, sensor_data: SensorData) -> bool:
        """Check whether manual override should be ignored for this cycle.

        The bypass only applies to covers that are explicitly part of the evening
        closure list and only while the evening closure signal is active.

        Args:
            sensor_data: Gathered sensor data for the current automation cycle

        Returns:
            True if evening closure should bypass manual override for this cover
        """

        evening_closure_reason = self._get_evening_closure_movement_reason(sensor_data)

        return self.resolved.evening_closure_ignore_manual_override_duration and (
            evening_closure_reason == CoverMovementReason.CLOSING_AFTER_SUNSET
        )

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
        self, sensor_data: SensorData, sun_hitting: bool, current_pos: int, manual_override_just_expired: bool = False
    ) -> tuple[int, CoverMovementReason | None, bool]:
        """Calculate the desired cover position based on sensor data.

        Returns a tuple of (desired_position, movement_reason, lockout_protection_active).
        """

        lockout_protection_active = False
        effective_temp_hot = self._get_effective_temp_hot(sensor_data)
        heat_protection_state = self._get_heat_protection_state(effective_temp_hot, sensor_data.weather_sunny, sun_hitting)
        evening_closure_reason = self._get_evening_closure_movement_reason(sensor_data)
        last_automation_closing_reason = self._cover_pos_history_mgr.get_closed_by_automation_reason(self.entity_id)
        delayed_reopen_action = self._cover_pos_history_mgr.get_delayed_reopen_action(self.entity_id)
        time_now = datetime.now(timezone.utc)

        if evening_closure_reason is not None:
            self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
            # Evening closure mode - check lockout protection first
            if self._is_lockout_protection_active(evening_closure_reason):
                # Lockout protection active - keep current position (prevent closing)
                lockout_protection_active = True
                desired_pos = current_pos
                desired_pos_friendly_name = "keeping current position because lockout protection is active"
                movement_reason = None  # No movement when lockout active
            else:
                # No lockout - close the cover
                max_closure_limit = self._get_cover_closure_limit(get_max=True, evening_closure=True)
                desired_pos = max(const.COVER_POS_FULLY_CLOSED, max_closure_limit)
                desired_pos_friendly_name = (
                    "closing for evening closure"
                    if evening_closure_reason == CoverMovementReason.CLOSING_AFTER_SUNSET
                    else "keeping the cover closed during the evening closure period"
                )
                movement_reason = evening_closure_reason
        elif heat_protection_state is True:
            self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
            # Heat protection mode - check lockout protection first
            if self._is_lockout_protection_active(CoverMovementReason.CLOSING_HEAT_PROTECTION):
                # Lockout protection active - keep current position (prevent closing)
                lockout_protection_active = True
                desired_pos = current_pos
                desired_pos_friendly_name = "keeping current position because lockout protection is active"
                movement_reason = None  # No movement when lockout active
            else:
                # No lockout - close the cover
                max_closure_limit = self._get_cover_closure_limit(get_max=True)
                desired_pos = max(const.COVER_POS_FULLY_CLOSED, max_closure_limit)
                desired_pos_friendly_name = "closing for heat protection"
                movement_reason = CoverMovementReason.CLOSING_HEAT_PROTECTION
        elif heat_protection_state is None:
            self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
            desired_pos = current_pos
            desired_pos_friendly_name = "keeping current position because required weather data is unavailable"
            movement_reason = None
        else:
            # Let light in mode - check if opening block after evening closure is active
            if self._has_missing_external_morning_opening_time(sensor_data):
                self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
                desired_pos = current_pos
                desired_pos_friendly_name = "keeping current position because external morning opening has no valid time"
                movement_reason = None
            elif self.entity_id in self.resolved.evening_closure_cover_list and self._is_opening_block_after_evening_closure_active(
                sensor_data
            ):
                self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
                # Opening block active - keep current position (no movement)
                desired_pos = current_pos
                desired_pos_friendly_name = "keeping current position because morning reopening is still blocked"
                movement_reason = None  # No movement reason when block active
            else:
                reopening_mode = self.resolved.automatic_reopening_mode
                open_target = min(const.COVER_POS_FULLY_OPEN, self._get_cover_closure_limit(get_max=False))
                reopening_allowed = reopening_mode == const.ReopeningMode.ACTIVE or (
                    reopening_mode == const.ReopeningMode.PASSIVE and last_automation_closing_reason is not None
                )

                if reopening_allowed and self._should_delay_heat_protection_reopen(last_automation_closing_reason):
                    delay_minutes = self.resolved.tilt_open_to_cover_open_delay
                    if delayed_reopen_action is None:
                        self._cover_pos_history_mgr.set_delayed_reopen_action(
                            self.entity_id,
                            reopen_at=time_now + timedelta(minutes=delay_minutes),
                        )
                        desired_pos = current_pos
                        desired_pos_friendly_name = "opening tilt before delayed reopening after heat protection"
                        movement_reason = CoverMovementReason.PREPARING_REOPEN_AFTER_HEAT_PROTECTION
                    elif time_now < delayed_reopen_action.reopen_at:
                        desired_pos = current_pos
                        desired_pos_friendly_name = "keeping current position until delayed reopening after heat protection expires"
                        movement_reason = CoverMovementReason.PREPARING_REOPEN_AFTER_HEAT_PROTECTION
                    else:
                        desired_pos = open_target
                        desired_pos_friendly_name = (
                            "already at the open target after delayed reopening"
                            if current_pos == desired_pos
                            else "opening because delayed reopening after heat protection has expired"
                        )
                        movement_reason = self._get_opening_movement_reason(
                            last_automation_closing_reason,
                            manual_override_just_expired=manual_override_just_expired,
                        )
                elif reopening_mode == const.ReopeningMode.ACTIVE:
                    self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
                    desired_pos = open_target
                    desired_pos_friendly_name = (
                        "already at the open target" if current_pos == desired_pos else "opening because closing conditions no longer apply"
                    )
                    movement_reason = self._get_opening_movement_reason(
                        last_automation_closing_reason,
                        manual_override_just_expired=manual_override_just_expired,
                    )
                elif reopening_mode == const.ReopeningMode.PASSIVE and last_automation_closing_reason is not None:
                    self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
                    desired_pos = open_target
                    desired_pos_friendly_name = (
                        "already at the open target after an automation-driven closure"
                        if current_pos == desired_pos
                        else "opening because this cover was previously closed by automation"
                    )
                    movement_reason = self._get_opening_movement_reason(
                        last_automation_closing_reason,
                        manual_override_just_expired=manual_override_just_expired,
                    )
                elif reopening_mode == const.ReopeningMode.PASSIVE:
                    self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
                    desired_pos = current_pos
                    desired_pos_friendly_name = (
                        "already at the open target"
                        if current_pos == open_target
                        else "keeping current position because passive reopening only applies after automation closed this cover"
                    )
                    movement_reason = None
                else:
                    self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
                    desired_pos = current_pos
                    desired_pos_friendly_name = (
                        "already at the open target"
                        if current_pos == open_target
                        else "keeping current position because automatic reopening is disabled"
                    )
                    movement_reason = None

        self._log_cover_msg(
            f"Current position: {current_pos}%, desired position: {desired_pos}%, {desired_pos_friendly_name}", const.LogSeverity.INFO
        )

        return desired_pos, movement_reason, lockout_protection_active

    def _should_delay_heat_protection_reopen(self, last_automation_closing_reason: str | None) -> bool:
        """Return whether this cover should use delayed reopening after heat protection."""

        if last_automation_closing_reason != const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION:
            return False

        if self.resolved.tilt_open_to_cover_open_delay <= 0:
            return False

        return self._get_effective_tilt_mode(is_night=False) == const.TiltMode.AUTO

    def _get_opening_movement_reason(
        self, last_automation_closing_reason: str | None, manual_override_just_expired: bool = False
    ) -> CoverMovementReason:
        """Map the last automation closing reason to the correct opening reason."""

        if last_automation_closing_reason == const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION:
            return CoverMovementReason.OPENING_AFTER_HEAT_PROTECTION

        if last_automation_closing_reason in (
            const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET,
            const.TRANSL_LOGBOOK_REASON_KEEP_CLOSED_AFTER_EVENING_CLOSURE,
        ):
            return CoverMovementReason.OPENING_AFTER_EVENING_CLOSURE

        if manual_override_just_expired:
            return CoverMovementReason.OPENING_AFTER_MANUAL_OVERRIDE

        return CoverMovementReason.OPENING_LET_LIGHT_IN

    #
    # _get_effective_temp_hot
    #
    def _get_effective_temp_hot(self, sensor_data: SensorData) -> bool | None:
        """Get the effective hot-weather state for this cover.

        Per-cover external control overrides the global hot state for this one
        cover only. When no per-cover override is configured, the global state
        from sensor_data is used as-is.

        Args:
            sensor_data: Sensor snapshot for the current automation cycle.

        Returns:
            Effective hot-weather state for this cover.
        """

        per_cover_key = f"{self.entity_id}_{const.COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"
        per_cover_override = self.config.get(per_cover_key)
        if per_cover_override is not None:
            effective_temp_hot = bool(per_cover_override)
            self._log_cover_msg(
                f"Per-cover weather hot external control active: {'hot' if effective_temp_hot else 'not hot'}",
                const.LogSeverity.DEBUG,
            )
            return effective_temp_hot

        return sensor_data.temp_hot

    @staticmethod
    def _get_heat_protection_state(
        effective_temp_hot: bool | None,
        weather_sunny: bool | None,
        sun_hitting: bool,
    ) -> bool | None:
        """Resolve whether heat-protection conditions are met.

        Returns True when all closing conditions are known to be active, False
        when any condition is known to be inactive, and None when a weather-
        dependent condition is unavailable while the sun is still hitting.
        """

        if not sun_hitting:
            return False

        if effective_temp_hot is False or weather_sunny is False:
            return False

        if effective_temp_hot is True and weather_sunny is True:
            return True

        return None

    #
    # _get_cover_closure_limit
    #
    def _get_cover_closure_limit(self, get_max: bool, evening_closure: bool = False) -> int:
        """Get the closure limit for this cover.

        Checks for per-cover override first, then falls back to global config.

        Args:
            get_max: If True, get max closure limit (for closing), otherwise min (for opening)
            evening_closure: If True, use the evening-closure-specific max setting path.

        Returns:
            Closure limit position (0-100)
        """

        if get_max and evening_closure:
            per_cover_key = f"{self.entity_id}_{const.COVER_SFX_EVENING_CLOSURE_MAX_CLOSURE}"
            global_default = self.resolved.evening_closure_max_closure
        elif get_max:
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
            if self._is_opening_movement_reason(movement_reason):
                self._cover_pos_history_mgr.clear_closed_by_automation(self.entity_id)
                self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
            return False, None, "No movement needed"

        if abs(desired_pos - current_pos) < self.resolved.covers_min_position_delta:
            if self._is_opening_movement_reason(movement_reason):
                self._cover_pos_history_mgr.clear_closed_by_automation(self.entity_id)
                self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)
            return False, None, "Skipped minor adjustment"

        # Movement needed
        try:
            # Move the cover
            actual_pos = await self._ha_interface.set_cover_position(self.entity_id, desired_pos, features)
            self._logger.debug(f"[{self.entity_id}] Actual position: {actual_pos}%")

            # Add the new position to the history
            self._cover_pos_history_mgr.add(self.entity_id, actual_pos, cover_moved=True)
            self._record_recent_automation_action(actual_pos)

            if movement_reason in (
                CoverMovementReason.CLOSING_HEAT_PROTECTION,
                CoverMovementReason.CLOSING_AFTER_SUNSET,
                CoverMovementReason.CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE,
            ):
                self._cover_pos_history_mgr.mark_closed_by_automation(
                    self.entity_id,
                    self._get_closing_logbook_reason_key(movement_reason),
                )
            else:
                self._cover_pos_history_mgr.clear_closed_by_automation(self.entity_id)

            if self._is_opening_movement_reason(movement_reason):
                self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)

            if movement_reason == CoverMovementReason.CLOSING_HEAT_PROTECTION:
                verb_key = const.TRANSL_LOGBOOK_VERB_CLOSING
                reason_key = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION
            elif movement_reason == CoverMovementReason.OPENING_LET_LIGHT_IN:
                verb_key = const.TRANSL_LOGBOOK_VERB_OPENING
                reason_key = const.TRANSL_LOGBOOK_REASON_LET_LIGHT_IN
            elif movement_reason == CoverMovementReason.OPENING_AFTER_HEAT_PROTECTION:
                verb_key = const.TRANSL_LOGBOOK_VERB_OPENING
                reason_key = const.TRANSL_LOGBOOK_REASON_END_HEAT_PROTECTION
            elif movement_reason == CoverMovementReason.OPENING_AFTER_MANUAL_OVERRIDE:
                verb_key = const.TRANSL_LOGBOOK_VERB_OPENING
                reason_key = const.TRANSL_LOGBOOK_REASON_END_MANUAL_OVERRIDE
            elif movement_reason == CoverMovementReason.OPENING_AFTER_EVENING_CLOSURE:
                verb_key = const.TRANSL_LOGBOOK_VERB_OPENING
                reason_key = const.TRANSL_LOGBOOK_REASON_END_EVENING_CLOSURE
            elif movement_reason == CoverMovementReason.CLOSING_AFTER_SUNSET:
                verb_key = const.TRANSL_LOGBOOK_VERB_CLOSING
                reason_key = const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET
            elif movement_reason == CoverMovementReason.CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE:
                verb_key = const.TRANSL_LOGBOOK_VERB_CLOSING
                reason_key = const.TRANSL_LOGBOOK_REASON_KEEP_CLOSED_AFTER_EVENING_CLOSURE
            elif movement_reason == CoverMovementReason.PREPARING_REOPEN_AFTER_HEAT_PROTECTION:
                # This state is used for tilt-only reopening preparation and should
                # never reach the cover movement path.
                return False, None, "Skipped cover movement during delayed reopen preparation"
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

    @staticmethod
    def _is_opening_movement_reason(movement_reason: CoverMovementReason) -> bool:
        """Return whether a movement reason represents reopening the cover."""

        return movement_reason in (
            CoverMovementReason.OPENING_LET_LIGHT_IN,
            CoverMovementReason.OPENING_AFTER_HEAT_PROTECTION,
            CoverMovementReason.OPENING_AFTER_MANUAL_OVERRIDE,
            CoverMovementReason.OPENING_AFTER_EVENING_CLOSURE,
        )

    @staticmethod
    def _get_closing_logbook_reason_key(movement_reason: CoverMovementReason) -> str:
        """Map a closing movement reason to the corresponding logbook reason key."""

        if movement_reason == CoverMovementReason.CLOSING_HEAT_PROTECTION:
            return const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION

        if movement_reason == CoverMovementReason.CLOSING_AFTER_SUNSET:
            return const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET

        if movement_reason == CoverMovementReason.CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE:
            return const.TRANSL_LOGBOOK_REASON_KEEP_CLOSED_AFTER_EVENING_CLOSURE

        raise ValueError(f"Unsupported closing movement reason: {movement_reason}")

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

        self._cover_pos_history_mgr.clear_closed_by_automation(self.entity_id)
        self._cover_pos_history_mgr.clear_delayed_reopen_action(self.entity_id)

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
                    self._record_recent_automation_action(const.COVER_POS_FULLY_OPEN)
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
                    self._record_recent_automation_action(const.COVER_POS_FULLY_CLOSED)
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
            self._record_recent_automation_action(new_pos)

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

    @staticmethod
    def _map_auto_tilt_to_ha_position(
        semantic_tilt: int,
        vertical_position: int,
        horizontal_position: int,
    ) -> int:
        """Map semantic Auto tilt to the cover's raw Home Assistant tilt scale.

        Args:
            semantic_tilt: Auto tilt on the semantic scale where 0 means vertical
                slats and 100 means horizontal slats.
            vertical_position: Raw HA tilt percentage that corresponds to vertical
                slats for this installation.
            horizontal_position: Raw HA tilt percentage that corresponds to
                horizontal slats for this installation.

        Returns:
            Raw HA tilt percentage clamped to 0-100.
        """

        semantic_tilt = max(const.COVER_POS_FULLY_CLOSED, min(const.COVER_POS_FULLY_OPEN, semantic_tilt))
        mapped = vertical_position + ((horizontal_position - vertical_position) * (semantic_tilt / 100.0))
        return max(const.COVER_POS_FULLY_CLOSED, min(const.COVER_POS_FULLY_OPEN, round(mapped)))

    #
    # _get_external_tilt_value
    #
    def _get_external_tilt_value(self, is_night: bool) -> int | None:
        """Resolve the active external tilt value for this cover.

        Per-cover external tilt values are only considered when the cover has an
        explicit per-cover external mode override. Otherwise the matching global
        external tilt value is used.

        Args:
            is_night: True when evaluating night/evening closure, False for day.

        Returns:
            Tilt value between 0 and 100, or None when no external value exists.
        """

        def _validate_external_tilt_value(raw_value: Any, config_key: str) -> int | None:
            """Convert and validate one external tilt value.

            Invalid or out-of-range values are ignored so they never reach the
            service layer.
            """

            tilt_value = to_int_or_none(raw_value)
            if tilt_value is None:
                if raw_value is not None:
                    self._log_cover_msg(
                        f"Invalid external tilt value for {config_key}: {raw_value!r}, skipping",
                        const.LogSeverity.WARNING,
                    )
                return None

            if not (const.COVER_POS_FULLY_CLOSED <= tilt_value <= const.COVER_POS_FULLY_OPEN):
                self._log_cover_msg(
                    f"External tilt value out of range for {config_key}: {tilt_value}, skipping",
                    const.LogSeverity.WARNING,
                )
                return None

            return tilt_value

        if is_night:
            per_cover_mode_suffix = const.COVER_SFX_TILT_MODE_NIGHT
            per_cover_value_suffix = const.COVER_SFX_TILT_EXTERNAL_VALUE_NIGHT
            global_value_key = const.NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT
        else:
            per_cover_mode_suffix = const.COVER_SFX_TILT_MODE_DAY
            per_cover_value_suffix = const.COVER_SFX_TILT_EXTERNAL_VALUE_DAY
            global_value_key = const.NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY

        per_cover_mode_key = f"{self.entity_id}_{per_cover_mode_suffix}"
        if self.config.get(per_cover_mode_key) == const.TiltMode.EXTERNAL:
            per_cover_value_key = f"{self.entity_id}_{per_cover_value_suffix}"
            return _validate_external_tilt_value(self.config.get(per_cover_value_key), per_cover_value_key)

        return _validate_external_tilt_value(self.config.get(global_value_key), global_value_key)

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
        is_night = movement_reason in (
            CoverMovementReason.CLOSING_AFTER_SUNSET,
            CoverMovementReason.CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE,
        )
        tilt_mode = self._get_effective_tilt_mode(is_night)

        if tilt_mode is None:
            return  # Cover doesn't support tilt

        # Skip tilt when cover is fully open (raised) — slats are not deployed
        effective_pos = cover_state.pos_target_final if cover_moved else cover_state.pos_current
        if effective_pos == const.COVER_POS_FULLY_OPEN:
            return

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
            if sensor_data.weather_sunny is None:
                if cover_state.sun_hitting:
                    self._log_cover_msg("Auto tilt skipped because sunshine state is unavailable", const.LogSeverity.DEBUG)
                    return
                target_tilt = self._map_auto_tilt_to_ha_position(
                    const.COVER_POS_FULLY_OPEN,
                    self.resolved.tilt_vertical_position,
                    self.resolved.tilt_horizontal_position,
                )
            elif sensor_data.weather_sunny and cover_state.sun_hitting and cover_state.sun_azimuth_diff is not None:
                semantic_tilt = self._calculate_auto_tilt(
                    sensor_data.sun_elevation,
                    cover_state.sun_azimuth_diff,
                    self.resolved.tilt_slat_overlap_ratio,
                )
                target_tilt = self._map_auto_tilt_to_ha_position(
                    semantic_tilt,
                    self.resolved.tilt_vertical_position,
                    self.resolved.tilt_horizontal_position,
                )
            else:
                # Sun not hitting or not sunny — open tilt fully to let in diffuse daylight
                target_tilt = self._map_auto_tilt_to_ha_position(
                    const.COVER_POS_FULLY_OPEN,
                    self.resolved.tilt_vertical_position,
                    self.resolved.tilt_horizontal_position,
                )
        elif tilt_mode == const.TiltMode.EXTERNAL:
            target_tilt = self._get_external_tilt_value(is_night)
            if target_tilt is None:
                self._log_cover_msg("External tilt mode active but no external value is set, skipping", const.LogSeverity.DEBUG)
                return
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
            self._record_recent_automation_action(effective_pos)
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
