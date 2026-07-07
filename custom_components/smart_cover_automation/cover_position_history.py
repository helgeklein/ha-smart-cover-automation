"""Position history tracking for covers."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

from . import const
from .movement import AutomationManagedState, AutomationMode


@dataclass(frozen=True, slots=True)
class PositionEntry:
    """A single position entry with timestamp."""

    position: int
    cover_moved: bool
    timestamp: datetime
    tilt_position: int | None = None


@dataclass(frozen=True, slots=True)
class RecentAutomationAction:
    """Short-lived tracking for expected position drift after recent automation."""

    expected_position: int
    allowed_position_drift: int
    expires_at: datetime
    expected_tilt_position: int | None = None
    allowed_tilt_drift: int = 0


@dataclass(frozen=True, slots=True)
class DelayedReopenAction:
    """Short-lived tracking for delayed reopening after tilt was opened."""

    reopen_at: datetime


@dataclass(slots=True)
class CoverPositionHistory:
    """Tracks position history for a single cover."""

    _entries: deque[PositionEntry] = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the deque after the object is created."""
        self._entries: deque[PositionEntry] = deque(maxlen=const.COVER_POSITION_HISTORY_SIZE)

    def add_position(
        self,
        position: int,
        cover_moved: bool,
        timestamp: datetime | None = None,
        tilt_position: int | None = None,
    ) -> PositionEntry:
        """Add a new position to the history (newest first).

        Args:
            position: The cover position
            cover_moved: Whether the cover was actually moved in this update cycle
            timestamp: UTC timestamp, defaults to current UTC time if None
            tilt_position: Current tilt position, if known

        Returns:
            The newly created PositionEntry that was added to the history
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        entry = PositionEntry(position, cover_moved, timestamp, tilt_position)
        self._entries.appendleft(entry)
        return entry

    def get_newest_entry(self) -> PositionEntry | None:
        """Get the newest (most recent) position entry with timestamp."""
        return self._entries[0] if self._entries else None

    def get_all_entries(self) -> list[PositionEntry]:
        """Get all position entries with timestamps from newest to oldest."""
        return list(self._entries)

    def __bool__(self) -> bool:
        """Return True if history contains any positions."""
        return bool(self._entries)

    def __len__(self) -> int:
        """Return the number of positions in history."""
        return len(self._entries)

    def __iter__(self) -> Iterator[int]:
        """Make the object iterable to support list() conversion and direct iteration."""
        return iter(entry.position for entry in self._entries)


#
# CoverPositionHistoryManager
#
class CoverPositionHistoryManager:
    """Manages position history for all covers in the coordinator."""

    __slots__ = (
        "_automation_managed_states",
        "_cover_position_history",
        "_delayed_reopen_actions",
        "_manual_override_blocked",
        "_on_automation_managed_states_changed",
        "_recent_automation_actions",
    )

    def __init__(
        self,
        on_automation_managed_states_changed: Callable[[dict[str, dict[str, Any]]], None] | None = None,
        on_closed_by_automation_changed: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        """Initialize the position history manager."""
        if on_automation_managed_states_changed is None and on_closed_by_automation_changed is not None:
            on_automation_managed_states_changed = lambda _states: on_closed_by_automation_changed(  # noqa: E731
                self.export_closed_by_automation_markers()
            )

        self._automation_managed_states: dict[str, AutomationManagedState] = {}
        self._cover_position_history: dict[str, CoverPositionHistory] = {}
        self._delayed_reopen_actions: dict[str, DelayedReopenAction] = {}
        self._manual_override_blocked: set[str] = set()
        self._on_automation_managed_states_changed = on_automation_managed_states_changed
        self._recent_automation_actions: dict[str, RecentAutomationAction] = {}

    def _notify_automation_managed_states_changed(self) -> None:
        """Persist automation-managed states when they change."""

        if self._on_automation_managed_states_changed is None:
            return

        self._on_automation_managed_states_changed(self.export_automation_managed_states())

    #
    # add
    #
    def add(
        self,
        entity_id: str,
        new_position: int,
        cover_moved: bool,
        timestamp: datetime | None = None,
        tilt_position: int | None = None,
    ) -> None:
        """Add a new cover position to the history.

        Args:
            entity_id: The cover entity ID
            new_position: The new position to add to history
            cover_moved: Whether the cover was actually moved in this update cycle
            timestamp: UTC timestamp, defaults to current UTC time if None
            tilt_position: Current tilt position, if known
        """
        if entity_id not in self._cover_position_history:
            # First time seeing this cover - initialize with new history object
            self._cover_position_history[entity_id] = CoverPositionHistory()

        # Add the new position to the history
        history = self._cover_position_history[entity_id]
        history.add_position(new_position, cover_moved, timestamp, tilt_position)

    #
    # get_entries
    #
    def get_entries(self, entity_id: str) -> list[PositionEntry]:
        """Get the position history entries with timestamps for a cover.

        Args:
            entity_id: The cover entity ID

        Returns:
            List with all position entries in order from newest to oldest
        """
        history = self._cover_position_history.get(entity_id)
        if history:
            return history.get_all_entries()
        else:
            return []

    #
    # get_latest_entry
    #
    def get_latest_entry(self, entity_id: str) -> PositionEntry | None:
        """Get the latest (newest) position entry with timestamp from the cover position history.

        Args:
            entity_id: The cover entity ID

        Returns:
            The newest position entry or None if no history exists
        """
        history = self._cover_position_history.get(entity_id)
        if history:
            return history.get_newest_entry()
        else:
            return None

    #
    # set_recent_automation_action
    #
    def set_recent_automation_action(
        self,
        entity_id: str,
        expected_position: int,
        allowed_position_drift: int,
        expires_at: datetime,
        expected_tilt_position: int | None = None,
        allowed_tilt_drift: int = 0,
    ) -> None:
        """Store a short-lived expected position drift after recent automation.

        Args:
            entity_id: The cover entity ID
            expected_position: The pre-drift position commanded by automation
            allowed_position_drift: Allowed deviation around the expected position
            expires_at: UTC timestamp when the tolerance window expires
            expected_tilt_position: The tilt commanded by automation, if any
            allowed_tilt_drift: Allowed deviation around the expected tilt position
        """

        self._recent_automation_actions[entity_id] = RecentAutomationAction(
            expected_position=expected_position,
            allowed_position_drift=allowed_position_drift,
            expires_at=expires_at,
            expected_tilt_position=expected_tilt_position,
            allowed_tilt_drift=allowed_tilt_drift,
        )

    #
    # get_recent_automation_action
    #
    def get_recent_automation_action(self, entity_id: str) -> RecentAutomationAction | None:
        """Get the active recent automation action for a cover, if any."""

        return self._recent_automation_actions.get(entity_id)

    #
    # clear_recent_automation_action
    #
    def clear_recent_automation_action(self, entity_id: str) -> None:
        """Clear any stored recent automation action for a cover."""

        self._recent_automation_actions.pop(entity_id, None)

    def set_delayed_reopen_action(self, entity_id: str, reopen_at: datetime) -> None:
        """Store a delayed reopen deadline for a cover."""

        self._delayed_reopen_actions[entity_id] = DelayedReopenAction(reopen_at=reopen_at)

    def get_delayed_reopen_action(self, entity_id: str) -> DelayedReopenAction | None:
        """Get the active delayed reopen state for a cover, if any."""

        return self._delayed_reopen_actions.get(entity_id)

    def clear_delayed_reopen_action(self, entity_id: str) -> None:
        """Clear any stored delayed reopen state for a cover."""

        self._delayed_reopen_actions.pop(entity_id, None)

    def set_automation_managed_state(self, entity_id: str, state: AutomationManagedState) -> None:
        """Store the current automation-managed state for a cover."""

        if self._automation_managed_states.get(entity_id) == state:
            return

        self._automation_managed_states[entity_id] = state
        self._notify_automation_managed_states_changed()

    def get_automation_managed_state(self, entity_id: str) -> AutomationManagedState | None:
        """Return the current automation-managed state for a cover."""

        return self._automation_managed_states.get(entity_id)

    def clear_automation_managed_state(self, entity_id: str) -> None:
        """Clear the current automation-managed state for a cover."""

        if entity_id not in self._automation_managed_states:
            return

        self._automation_managed_states.pop(entity_id, None)
        self._notify_automation_managed_states_changed()

    def was_closed_by_automation(self, entity_id: str) -> bool:
        """Return whether the cover is currently marked as automation-closed."""

        return entity_id in self._automation_managed_states

    def get_closed_by_automation_reason(self, entity_id: str) -> str | None:
        """Return the stored automation-closing reason key for a cover, if any."""

        managed_state = self.get_automation_managed_state(entity_id)
        if managed_state is None:
            return None

        return _legacy_reason_key_for_automation_mode(managed_state.automation_mode)

    def get_automation_owned_position(self, entity_id: str) -> int | None:
        """Return the automation-owned position for a cover, if any."""

        managed_state = self.get_automation_managed_state(entity_id)
        return None if managed_state is None else managed_state.position

    def set_automation_owned_position(self, entity_id: str, position: int) -> None:
        """Update the owned position while preserving the existing managed cause."""

        managed_state = self.get_automation_managed_state(entity_id)
        if managed_state is None:
            return

        self.set_automation_managed_state(
            entity_id,
            AutomationManagedState(position=position, automation_mode=managed_state.automation_mode),
        )

    def mark_closed_by_automation(self, entity_id: str, reason_key: str) -> None:
        """Legacy compatibility wrapper for tests and migration paths."""

        automation_mode = _movement_cause_for_legacy_reason_key(reason_key)
        if automation_mode is None:
            return

        current_state = self.get_automation_managed_state(entity_id)
        if current_state is None:
            self.set_automation_managed_state(
                entity_id,
                AutomationManagedState(position=const.COVER_POS_FULLY_CLOSED, automation_mode=automation_mode),
            )
            return

        self.set_automation_managed_state(
            entity_id,
            AutomationManagedState(position=current_state.position, automation_mode=automation_mode),
        )

    def clear_closed_by_automation(self, entity_id: str) -> None:
        """Legacy compatibility wrapper for clearing automation-managed state."""

        self.clear_automation_managed_state(entity_id)

    def export_closed_by_automation_markers(self) -> dict[str, str]:
        """Return a legacy marker export derived from automation-managed state."""

        return {
            entity_id: reason_key
            for entity_id, state in self._automation_managed_states.items()
            if (reason_key := _legacy_reason_key_for_automation_mode(state.automation_mode)) is not None
        }

    def export_automation_managed_states(self) -> dict[str, dict[str, Any]]:
        """Return automation-managed state as a persistence-friendly payload."""

        return {
            entity_id: {"position": state.position, "automation_mode": state.automation_mode.value}
            for entity_id, state in self._automation_managed_states.items()
        }

    def restore_closed_by_automation_markers(self, markers: Mapping[str, str]) -> None:
        """Restore only the legacy close markers for compatibility.

        This intentionally restores reason intent only. Position bootstrap belongs
        in the higher-level restore flow that can inspect live entity state.
        """

        restored: dict[str, AutomationManagedState] = {}
        for entity_id, reason_key in markers.items():
            automation_mode = _movement_cause_for_legacy_reason_key(reason_key)
            if not isinstance(entity_id, str) or automation_mode is None:
                continue
            restored[entity_id] = AutomationManagedState(position=const.COVER_POS_FULLY_CLOSED, automation_mode=automation_mode)

        self._automation_managed_states = restored

    def restore_automation_managed_states(self, states: Mapping[str, Mapping[str, Any]]) -> set[str]:
        """Restore automation-managed states from persistent storage.

        Returns the entity IDs whose managed state payload restored successfully.
        """

        restored: dict[str, AutomationManagedState] = {}
        for entity_id, payload in states.items():
            if not isinstance(entity_id, str) or not isinstance(payload, Mapping):
                continue

            raw_position = payload.get("position")
            raw_automation_mode = payload.get("automation_mode")
            if raw_automation_mode is None:
                raw_automation_mode = payload.get("cause")
            if not isinstance(raw_position, int) or not isinstance(raw_automation_mode, str):
                continue

            automation_mode = _automation_mode_for_persisted_value(raw_automation_mode)
            if automation_mode is None:
                continue

            restored[entity_id] = AutomationManagedState(position=raw_position, automation_mode=automation_mode)

        self._automation_managed_states = restored
        return set(restored)

    def has_automation_managed_states(self) -> bool:
        """Return whether any valid managed state is currently stored."""

        return bool(self._automation_managed_states)

    def mark_manual_override_blocked(self, entity_id: str) -> None:
        """Mark that automation is currently blocked by a manual override."""

        self._manual_override_blocked.add(entity_id)

    def clear_manual_override_blocked(self, entity_id: str) -> None:
        """Clear the manual-override-blocked marker for a cover."""

        self._manual_override_blocked.discard(entity_id)

    def was_manual_override_blocking(self, entity_id: str) -> bool:
        """Return whether the cover was previously blocked by manual override."""

        return entity_id in self._manual_override_blocked


def _movement_cause_for_legacy_reason_key(reason_key: str) -> AutomationMode | None:
    """Translate legacy persisted/logbook reason keys into automation modes."""

    if reason_key == const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION:
        return AutomationMode.HEAT_PROTECTION
    if reason_key == const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET:
        return AutomationMode.EVENING_CLOSURE
    if reason_key == const.TRANSL_LOGBOOK_REASON_KEEP_CLOSED_AFTER_EVENING_CLOSURE:
        return AutomationMode.EVENING_CLOSURE
    return None


def _legacy_reason_key_for_automation_mode(automation_mode: AutomationMode) -> str | None:
    """Translate an automation mode into the legacy persisted/logbook reason key."""

    if automation_mode == AutomationMode.HEAT_PROTECTION:
        return const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION
    if automation_mode == AutomationMode.EVENING_CLOSURE:
        return const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET
    return None


def _automation_mode_for_persisted_value(raw_value: str) -> AutomationMode | None:
    """Translate persisted managed-state values into automation modes."""

    try:
        return AutomationMode(raw_value)
    except ValueError:
        return _movement_cause_for_legacy_reason_key(raw_value)
