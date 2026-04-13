"""Persistent storage for runtime automation state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from homeassistant.helpers.storage import Store

from . import const
from .log import Log


class AutomationStateStore:
    """Persist automation state that must survive Home Assistant restarts."""

    _fallback_storage: ClassVar[dict[str, dict[str, str]]] = {}

    def __init__(self, hass: Any, entry_id: str) -> None:
        """Initialize the store for one config entry."""

        self._entry_id = entry_id
        self._logger = Log(entry_id=entry_id)
        self._store: Store[dict[str, Any]] | None = None

        try:
            getattr(hass, "data")
            getattr(hass, "config")
        except AttributeError:
            return

        self._store = Store(
            hass,
            const.STORAGE_VERSION,
            f"{const.DOMAIN}.{entry_id}.{const.STORAGE_KEY_AUTOMATION_STATE}",
        )

    async def async_load_closed_markers(self) -> dict[str, str]:
        """Load automation-closed markers from persistent storage."""

        if self._store is None:
            return dict(self._fallback_storage.get(self._entry_id, {}))

        try:
            data = await self._store.async_load()
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to load persisted automation state: %s", err)
            return {}

        if not isinstance(data, dict):
            return {}

        raw_markers = data.get(const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS)
        if not isinstance(raw_markers, dict):
            return {}

        return {
            entity_id: reason_key
            for entity_id, reason_key in raw_markers.items()
            if isinstance(entity_id, str) and isinstance(reason_key, str)
        }

    def schedule_save_closed_markers(self, markers: Mapping[str, str]) -> None:
        """Schedule persistence for the current automation-closed markers."""

        snapshot = dict(markers)
        if self._store is None:
            self._fallback_storage[self._entry_id] = snapshot
            return

        try:
            self._store.async_delay_save(
                lambda: {const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS: snapshot},
                const.STORAGE_SAVE_DELAY_SECONDS,
            )
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to schedule persisted automation state save: %s", err)

    async def async_save_closed_markers(self, markers: Mapping[str, str]) -> None:
        """Immediately persist the current automation-closed markers."""

        snapshot = dict(markers)
        if self._store is None:
            self._fallback_storage[self._entry_id] = snapshot
            return

        try:
            await self._store.async_save({const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS: snapshot})
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to persist automation state: %s", err)

    async def async_remove(self) -> None:
        """Remove persisted automation state for this config entry."""

        if self._store is None:
            self._fallback_storage.pop(self._entry_id, None)
            return

        try:
            await self._store.async_remove()
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to remove persisted automation state: %s", err)
