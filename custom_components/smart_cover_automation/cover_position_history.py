"""Position history tracking for covers."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from . import const


@dataclass(frozen=True, slots=True)
class PositionEntry:
    """A single position entry with timestamp."""

    position: int
    cover_moved: bool
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class RecentAutomationAction:
    """Short-lived tracking for expected position drift after recent automation."""

    expected_position: int
    allowed_position_drift: int
    expires_at: datetime


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

    def add_position(self, position: int, cover_moved: bool, timestamp: datetime | None = None) -> PositionEntry:
        """Add a new position to the history (newest first).

        Args:
            position: The cover position
            cover_moved: Whether the cover was actually moved in this update cycle
            timestamp: UTC timestamp, defaults to current UTC time if None

        Returns:
            The newly created PositionEntry that was added to the history
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        entry = PositionEntry(position, cover_moved, timestamp)
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
        "_automation_closed_markers",
        "_cover_position_history",
        "_delayed_reopen_actions",
        "_manual_override_blocked",
        "_on_closed_by_automation_changed",
        "_recent_automation_actions",
    )

    def __init__(self, on_closed_by_automation_changed: Callable[[dict[str, str]], None] | None = None) -> None:
        """Initialize the position history manager."""
        self._automation_closed_markers: dict[str, str] = {}
        self._cover_position_history: dict[str, CoverPositionHistory] = {}
        self._delayed_reopen_actions: dict[str, DelayedReopenAction] = {}
        self._manual_override_blocked: set[str] = set()
        self._on_closed_by_automation_changed = on_closed_by_automation_changed
        self._recent_automation_actions: dict[str, RecentAutomationAction] = {}

    def _notify_closed_by_automation_changed(self) -> None:
        """Persist automation-closed markers when they change."""

        if self._on_closed_by_automation_changed is None:
            return

        self._on_closed_by_automation_changed(dict(self._automation_closed_markers))

    #
    # add
    #
    def add(self, entity_id: str, new_position: int, cover_moved: bool, timestamp: datetime | None = None) -> None:
        """Add a new cover position to the history.

        Args:
            entity_id: The cover entity ID
            new_position: The new position to add to history
            cover_moved: Whether the cover was actually moved in this update cycle
            timestamp: UTC timestamp, defaults to current UTC time if None
        """
        if entity_id not in self._cover_position_history:
            # First time seeing this cover - initialize with new history object
            self._cover_position_history[entity_id] = CoverPositionHistory()

        # Add the new position to the history
        history = self._cover_position_history[entity_id]
        history.add_position(new_position, cover_moved, timestamp)

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
    ) -> None:
        """Store a short-lived expected position drift after recent automation.

        Args:
            entity_id: The cover entity ID
            expected_position: The pre-drift position commanded by automation
            allowed_position_drift: Allowed deviation around the expected position
            expires_at: UTC timestamp when the tolerance window expires
        """

        self._recent_automation_actions[entity_id] = RecentAutomationAction(
            expected_position=expected_position,
            allowed_position_drift=allowed_position_drift,
            expires_at=expires_at,
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

    def mark_closed_by_automation(self, entity_id: str, reason_key: str) -> None:
        """Mark a cover as currently closed by automation and remember why."""

        if self._automation_closed_markers.get(entity_id) == reason_key:
            return

        self._automation_closed_markers[entity_id] = reason_key
        self._notify_closed_by_automation_changed()

    def clear_closed_by_automation(self, entity_id: str) -> None:
        """Clear the automation-closed marker for a cover."""

        if entity_id not in self._automation_closed_markers:
            return

        self._automation_closed_markers.pop(entity_id, None)
        self._notify_closed_by_automation_changed()

    def was_closed_by_automation(self, entity_id: str) -> bool:
        """Return whether the cover is currently marked as automation-closed."""

        return entity_id in self._automation_closed_markers

    def get_closed_by_automation_reason(self, entity_id: str) -> str | None:
        """Return the stored automation-closing reason key for a cover, if any."""

        return self._automation_closed_markers.get(entity_id)

    def export_closed_by_automation_markers(self) -> dict[str, str]:
        """Return a copy of the automation-closed markers for persistence."""

        return dict(self._automation_closed_markers)

    def restore_closed_by_automation_markers(self, markers: Mapping[str, str]) -> None:
        """Restore automation-closed markers from persistent storage."""

        self._automation_closed_markers = {
            entity_id: reason_key for entity_id, reason_key in markers.items() if isinstance(entity_id, str) and isinstance(reason_key, str)
        }

    def mark_manual_override_blocked(self, entity_id: str) -> None:
        """Mark that automation is currently blocked by a manual override."""

        self._manual_override_blocked.add(entity_id)

    def clear_manual_override_blocked(self, entity_id: str) -> None:
        """Clear the manual-override-blocked marker for a cover."""

        self._manual_override_blocked.discard(entity_id)

    def was_manual_override_blocking(self, entity_id: str) -> bool:
        """Return whether the cover was previously blocked by manual override."""

        return entity_id in self._manual_override_blocked
