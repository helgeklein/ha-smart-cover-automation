"""Position history tracking for cover automation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterator

from . import const


@dataclass
class CoverPositionHistory:
    """Tracks position history for a single cover."""

    def __post_init__(self) -> None:
        """Initialize the deque after the object is created."""
        self._positions: deque[int | None] = deque(maxlen=const.COVER_POSITION_HISTORY_SIZE)

    def add_position(self, position: int | None) -> None:
        """Add a new position to the history (newest first)."""
        self._positions.appendleft(position)

    def get_newest(self) -> int | None:
        """Get the newest (most recent) position."""
        return self._positions[0] if self._positions else None

    def get_all(self) -> list[int | None]:
        """Get all positions from newest to oldest."""
        return list(self._positions)

    def __bool__(self) -> bool:
        """Return True if history contains any positions."""
        return bool(self._positions)

    def __len__(self) -> int:
        """Return the number of positions in history."""
        return len(self._positions)

    def __iter__(self) -> Iterator[int | None]:
        """Make the object iterable to support list() conversion and direct iteration."""
        return iter(self._positions)


class CoverPositionHistoryManager:
    """Manages position history for all covers in the coordinator."""

    def __init__(self) -> None:
        """Initialize the position history manager."""
        self._cover_position_history: dict[str, CoverPositionHistory] = {}

    def update(self, entity_id: str, new_position: int | None) -> None:
        """Update position history for a cover, maintaining the last COVER_POSITION_HISTORY_SIZE positions.

        Args:
            entity_id: The cover entity ID
            new_position: The new position to add to history
        """
        if entity_id not in self._cover_position_history:
            # First time seeing this cover - initialize with new history object
            self._cover_position_history[entity_id] = CoverPositionHistory()

        # Add the new position to the history
        history = self._cover_position_history[entity_id]
        history.add_position(new_position)

        const.LOGGER.debug(f"[{entity_id}] Updated position history: {history.get_all()} (current: {history.get_newest() or 'N/A'})")

    def get(self, entity_id: str) -> list[int | None]:
        """Get the position history for a cover.

        Args:
            entity_id: The cover entity ID

        Returns:
            List with all positions in order from newest to oldest
        """
        history = self._cover_position_history.get(entity_id)
        return history.get_all() if history else []

    def get_latest(self, entity_id: str) -> int | None:
        """Get the latest (newest) position from the cover position history.

        Args:
            entity_id: The cover entity ID

        Returns:
            The newest position value or None if no history exists
        """
        history = self._cover_position_history.get(entity_id)
        return history.get_newest() if history else None
