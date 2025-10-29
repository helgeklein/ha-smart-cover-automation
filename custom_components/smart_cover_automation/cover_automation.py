"""Cover automation logic for individual covers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

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
    from homeassistant.core import HomeAssistant, State


@dataclass
class SensorData:
    """Encapsulates sensor data gathered for an automation run."""

    sun_azimuth: float
    sun_elevation: float
    temp_max: float
    temp_hot: bool
    weather_condition: str
    weather_sunny: bool


class CoverAutomation:
    """Handles automation logic for a single cover."""

    #
    # __init__
    #
    def __init__(
        self,
        entity_id: str,
        hass: HomeAssistant,
        resolved: ResolvedConfig,
        config: dict[str, Any],
        cover_pos_history_mgr: CoverPositionHistoryManager,
        log_cover_result_callback: Any,
        set_cover_position_callback: Any,
        add_logbook_entry_callback: Any,
    ) -> None:
        """Initialize cover automation.

        Args:
            entity_id: Cover entity ID
            hass: Home Assistant instance
            resolved: Resolved configuration settings
            config: Raw configuration dictionary
            cover_pos_history_mgr: Cover position history manager
            log_cover_result_callback: Callback to log cover results (entity_id, message, cover_attrs)
            set_cover_position_callback: Callback to set cover position (entity_id, desired_pos, features) -> actual_pos
            add_logbook_entry_callback: Callback to add logbook entry (verb_key, entity_id, reason_key, target_pos)
        """

        self.entity_id = entity_id
        self.hass = hass
        self.resolved = resolved
        self.config = config
        self._cover_pos_history_mgr = cover_pos_history_mgr
        self._log_cover_result = log_cover_result_callback
        self._set_cover_position = set_cover_position_callback
        self._add_logbook_entry = add_logbook_entry_callback

    #
    # process
    #
    async def process(self, state: State | None, sensor_data: SensorData) -> dict[str, Any] | None:
        """Process automation for this cover.

        Args:
            state: Current state of the cover
            sensor_data: Gathered sensor data

        Returns:
            Dictionary of cover attributes or None if cover should be skipped
        """

        cover_attrs: dict[str, Any] = {}

        # Validate cover azimuth
        cover_azimuth = self._get_cover_azimuth(cover_attrs)
        if cover_azimuth is None:
            return None

        # Validate cover state
        if not self._validate_cover_state(state, cover_attrs):
            return None

        # Check if cover is moving
        if self._is_cover_moving(state):  # type: ignore[arg-type]
            return None

        # Get cover features and position
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)  # type: ignore[union-attr]
        cover_attrs[const.COVER_ATTR_SUPPORTED_FEATURES] = features

        current_pos = self._get_cover_position(state, features)  # type: ignore[arg-type]
        cover_attrs[const.COVER_ATTR_POS_CURRENT] = current_pos

        # Check for manual override
        if self._check_manual_override(current_pos):
            return cover_attrs

        # Calculate sun hitting
        sun_hitting, sun_azimuth_difference = self._calculate_sun_hitting(sensor_data.sun_azimuth, sensor_data.sun_elevation, cover_azimuth)
        cover_attrs[const.COVER_ATTR_SUN_HITTING] = sun_hitting
        cover_attrs[const.COVER_ATTR_SUN_AZIMUTH_DIFF] = sun_azimuth_difference

        # Calculate desired position
        desired_pos, desired_pos_friendly_name, verb_key, reason_key = self._calculate_desired_position(sensor_data, sun_hitting)

        cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = desired_pos
        const.LOGGER.debug(f"[{self.entity_id}] Desired position: {desired_pos}%, {desired_pos_friendly_name}")

        # Move cover if needed
        movement_needed, message = await self._move_cover_if_needed(current_pos, desired_pos, features, verb_key, reason_key, cover_attrs)

        if not movement_needed:
            # No movement - just add the current position to the history
            self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)

        # Include position history in cover attributes
        position_entries = self._cover_pos_history_mgr.get_entries(self.entity_id)
        cover_attrs[const.COVER_ATTR_POS_HISTORY] = [entry.position for entry in position_entries]

        # Log per-cover attributes
        const.LOGGER.debug(f"[{self.entity_id}] Cover result: {message}. Cover data: {str(cover_attrs)}")

        return cover_attrs

    #
    # _get_cover_azimuth
    #
    def _get_cover_azimuth(self, cover_attrs: dict[str, Any]) -> float | None:
        """Get and validate cover azimuth from configuration.

        Args:
            cover_attrs: Dictionary to store cover attributes

        Returns:
            Cover azimuth or None if invalid/missing
        """
        cover_azimuth_raw = self.config.get(f"{self.entity_id}_{const.COVER_SFX_AZIMUTH}")
        cover_azimuth = to_float_or_none(cover_azimuth_raw)
        if cover_azimuth is None:
            self._log_cover_result(self.entity_id, "Cover has invalid or missing azimuth (direction), skipping")
            return None
        cover_attrs[const.COVER_ATTR_COVER_AZIMUTH] = cover_azimuth
        return cover_azimuth

    #
    # _validate_cover_state
    #
    def _validate_cover_state(self, state: State | None, cover_attrs: dict[str, Any]) -> bool:
        """Validate cover state is usable for automation.

        Args:
            state: Cover state
            cover_attrs: Dictionary to store cover attributes

        Returns:
            True if state is valid, False otherwise
        """

        if state is None or state.state is None:
            self._log_cover_result(self.entity_id, "Cover state unavailable, skipping")
            return False
        if state.state in ("", STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._log_cover_result(self.entity_id, f"Cover state '{state.state}' unsupported, skipping")
            return False
        cover_attrs[const.COVER_ATTR_STATE] = state.state
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
            self._log_cover_result(self.entity_id, "Cover is currently moving, skipping")
        return is_moving

    #
    # _check_lockout_protection
    #
    def _check_lockout_protection(self, cover_attrs: dict[str, Any]) -> bool:
        """Check if lockout protection should be enforced for this cover.

        Lockout protection prevents cover closing when associated window sensors indicate
        that a window is open.

        Args:
            cover_attrs: Dictionary to store cover attributes

        Returns:
            True if lockout is active (should skip), False otherwise
        """

        # Get configured window sensors for this cover
        window_sensors_key = f"{self.entity_id}_{const.COVER_SFX_WINDOW_SENSORS}"
        window_sensors = self.config.get(window_sensors_key)

        # If no window sensors configured, no lockout protection needed
        if not window_sensors or not isinstance(window_sensors, list):
            cover_attrs[const.COVER_ATTR_LOCKOUT_PROTECTION] = False
            return False

        # Check if any window sensor indicates an open window
        open_sensors = []
        for sensor_id in window_sensors:
            sensor_state = self.hass.states.get(sensor_id)
            if sensor_state and sensor_state.state == STATE_ON:
                open_sensors.append(sensor_id)

        # If any window is open, activate lockout protection
        if open_sensors:
            cover_attrs[const.COVER_ATTR_LOCKOUT_PROTECTION] = True
            return True

        cover_attrs[const.COVER_ATTR_LOCKOUT_PROTECTION] = False
        return False

    #
    # _get_cover_position
    #
    def _get_cover_position(self, state: State, features: int) -> int:
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
                return pos
            # If position attribute is missing, fall through to state-based logic

        # Cover does not support position or position unavailable - infer from state
        # Normalize state to lowercase for case-insensitive comparison
        cover_state = state.state.lower() if state.state else None

        if cover_state == STATE_CLOSED:
            return const.COVER_POS_FULLY_CLOSED
        if cover_state == STATE_OPEN:
            return const.COVER_POS_FULLY_OPEN
        # Unknown state - assume open
        return const.COVER_POS_FULLY_OPEN

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
        last_history_entry = self._cover_pos_history_mgr.get_latest_entry(self.entity_id)
        if last_history_entry is not None and current_pos != last_history_entry.position:
            # Position has changed since our last recorded desired position
            # Beware of system time changes
            time_now = datetime.now(timezone.utc)
            if time_now > last_history_entry.timestamp:
                time_delta = (time_now - last_history_entry.timestamp).total_seconds()
                if time_delta < self.resolved.manual_override_duration:
                    time_remaining = self.resolved.manual_override_duration - time_delta
                    message = (
                        f"Manual override detected (position changed externally), skipping this cover for another {time_remaining:.0f} s"
                    )
                    self._log_cover_result(self.entity_id, message)
                    return True
        return False

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
    def _calculate_desired_position(self, sensor_data: SensorData, sun_hitting: bool) -> tuple[int, str, str, str]:
        """Calculate desired cover position based on conditions.

        Args:
            sensor_data: Current sensor data
            sun_hitting: Whether sun is hitting the window

        Returns:
            Tuple of (desired_position, friendly_name, verb_translation_key, reason_translation_key)
        """

        if sensor_data.temp_hot and sensor_data.weather_sunny and sun_hitting:
            # Heat protection mode - close the cover
            max_closure_limit = self._get_cover_closure_limit(get_max=True)
            desired_pos = max(const.COVER_POS_FULLY_CLOSED, max_closure_limit)
            desired_pos_friendly_name = "heat protection state (closed)"
            verb_key = const.TRANSL_LOGBOOK_VERB_CLOSING
            reason_key = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION
        else:
            # "Let light in" mode - open the cover
            min_closure_limit = self._get_cover_closure_limit(get_max=False)
            desired_pos = min(const.COVER_POS_FULLY_OPEN, min_closure_limit)
            desired_pos_friendly_name = "normal state (open)"
            verb_key = const.TRANSL_LOGBOOK_VERB_OPENING
            reason_key = const.TRANSL_LOGBOOK_REASON_LET_LIGHT_IN

        return desired_pos, desired_pos_friendly_name, verb_key, reason_key

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
        self,
        current_pos: int,
        desired_pos: int,
        features: int,
        verb_key: str,
        reason_key: str,
        cover_attrs: dict[str, Any],
    ) -> tuple[bool, str]:
        """Move cover if position change is significant enough.

        Args:
            current_pos: Current cover position
            desired_pos: Desired cover position
            features: Cover supported features
            verb_key: Translation key for logbook verb
            reason_key: Translation key for logbook reason
            cover_attrs: Dictionary to store cover attributes

        Returns:
            Tuple of (movement_needed, message)
        """

        # Determine if cover movement is necessary
        if desired_pos == current_pos:
            return False, "No movement needed"

        if abs(desired_pos - current_pos) < self.resolved.covers_min_position_delta:
            return False, "Skipped minor adjustment"

        # Check for lockout protection (window sensors)
        lockout_protection = self._check_lockout_protection(cover_attrs)
        if lockout_protection and verb_key == const.TRANSL_LOGBOOK_VERB_CLOSING:
            return False, "Lockout protection active, skipping closing"

        # Movement needed
        try:
            # Move the cover
            actual_pos = await self._set_cover_position(self.entity_id, desired_pos, features)
            const.LOGGER.debug(f"[{self.entity_id}] Actual position: {actual_pos}%")
            if actual_pos is not None:
                # Store the position after movement
                cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = actual_pos
                # Add the new position to the history
                self._cover_pos_history_mgr.add(self.entity_id, actual_pos, cover_moved=True)
                # Add detailed logbook entry
                await self._add_logbook_entry(
                    verb_key=verb_key,
                    entity_id=self.entity_id,
                    reason_key=reason_key,
                    target_pos=actual_pos,
                )
            return True, "Moved cover"
        except Exception as err:
            # Log the error but continue with other covers
            const.LOGGER.error(f"[{self.entity_id}] Failed to control cover: {err}")
            return False, f"Error: {err}"
