"""Position history tracking for cover        entry = PositionEntry(position=position, timestamp=timestamp)
    self._entries.appendleft(entry)

def get_newest_entry(self) -> PositionEntry | None:ion."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from . import const


@dataclass
class PositionEntry:
    """A single position entry with timestamp."""

    position: int
    cover_moved: bool
    timestamp: datetime


@dataclass
class CoverPositionHistory:
    """Tracks position history for a single cover."""

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


class CoverPositionHistoryManager:
    """Manages position history for all covers in the coordinator."""

    def __init__(self) -> None:
        """Initialize the position history manager."""
        self._cover_position_history: dict[str, CoverPositionHistory] = {}

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
        newest_entry = history.add_position(new_position, cover_moved, timestamp)

        # Log the new entry for debugging
        timestamp_str = newest_entry.timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        current_pos = newest_entry.position
        const.LOGGER.debug(f"[{entity_id}] Updated position history with new entry: {current_pos}% at {timestamp_str}")

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
