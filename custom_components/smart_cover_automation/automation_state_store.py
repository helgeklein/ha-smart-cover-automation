"""Persistent storage for runtime automation state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from homeassistant.helpers.storage import Store

from . import const
from .log import Log


class AutomationStateStore:
    """Persist automation state that must survive Home Assistant restarts."""

    _fallback_storage: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, hass: Any, entry_id: str) -> None:
        """Initialize the store for one config entry."""

        self._entry_id = entry_id
        self._logger = Log(entry_id=entry_id)
        self._store: Store[dict[str, Any]] | None = None
        self._state_cache: dict[str, Any] = {}

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

    async def _async_load_state(self) -> dict[str, Any]:
        """Load and validate the full persisted runtime-state payload."""

        if self._store is None:
            cached_data = self._fallback_storage.get(self._entry_id, {})
            return dict(cached_data) if isinstance(cached_data, dict) else {}

        try:
            loaded_data = await self._store.async_load()
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to load persisted automation state: %s", err)
            return {}

        if not isinstance(loaded_data, dict):
            return {}

        return dict(loaded_data)

    def _build_save_payload(self) -> dict[str, Any]:
        """Return a copy of the cached runtime-state payload."""

        return dict(self._state_cache)

    async def async_load_closed_markers(self) -> dict[str, str]:
        """Load automation-closed markers from persistent storage."""

        data = await self._async_load_state()
        self._state_cache = dict(data)

        raw_markers = data.get(const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS)
        if not isinstance(raw_markers, dict):
            return {}

        return {
            entity_id: reason_key
            for entity_id, reason_key in raw_markers.items()
            if isinstance(entity_id, str) and isinstance(reason_key, str)
        }

    async def async_load_current_day_temperature_extrema(self) -> dict[str, Any] | None:
        """Load current-day temperature extrema from persistent storage."""

        data = await self._async_load_state()
        self._state_cache = dict(data)

        raw_extrema = data.get(const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA)
        if not isinstance(raw_extrema, dict):
            return None

        raw_date = raw_extrema.get("date")
        raw_temp_max = raw_extrema.get("temp_max")
        raw_temp_min = raw_extrema.get("temp_min")
        if not isinstance(raw_date, str) or not isinstance(raw_temp_max, int | float):
            return None
        if raw_temp_min is not None and not isinstance(raw_temp_min, int | float):
            return None

        return {
            "date": raw_date,
            "temp_max": float(raw_temp_max),
            "temp_min": float(raw_temp_min) if raw_temp_min is not None else None,
        }

    def schedule_save_closed_markers(self, markers: Mapping[str, str]) -> None:
        """Schedule persistence for the current automation-closed markers."""

        snapshot = dict(markers)
        if self._store is None:
            payload = dict(self._fallback_storage.get(self._entry_id, {}))
            payload[const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS] = snapshot
            self._fallback_storage[self._entry_id] = payload
            self._state_cache = dict(payload)
            return

        self._state_cache[const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS] = snapshot

        try:
            self._store.async_delay_save(
                self._build_save_payload,
                const.STORAGE_SAVE_DELAY_SECONDS,
            )
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to schedule persisted automation state save: %s", err)

    def schedule_save_current_day_temperature_extrema(self, extrema: Mapping[str, Any] | None) -> None:
        """Schedule persistence for the current-day extrema snapshot."""

        snapshot = dict(extrema) if extrema is not None else None
        if self._store is None:
            payload = dict(self._fallback_storage.get(self._entry_id, {}))
            if snapshot is None:
                payload.pop(const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA, None)
            else:
                payload[const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA] = snapshot
            self._fallback_storage[self._entry_id] = payload
            self._state_cache = dict(payload)
            return

        if snapshot is None:
            self._state_cache.pop(const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA, None)
        else:
            self._state_cache[const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA] = snapshot

        try:
            self._store.async_delay_save(
                self._build_save_payload,
                const.STORAGE_SAVE_DELAY_SECONDS,
            )
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to schedule persisted automation state save: %s", err)

    async def async_save_closed_markers(self, markers: Mapping[str, str]) -> None:
        """Immediately persist the current automation-closed markers."""

        snapshot = dict(markers)
        if self._store is None:
            payload = dict(self._fallback_storage.get(self._entry_id, {}))
            payload[const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS] = snapshot
            self._fallback_storage[self._entry_id] = payload
            self._state_cache = dict(payload)
            return

        self._state_cache[const.STORAGE_KEY_AUTOMATION_CLOSED_MARKERS] = snapshot

        try:
            await self._store.async_save(self._build_save_payload())
        except (AttributeError, OSError, TypeError, ValueError) as err:
            self._logger.warning("Failed to persist automation state: %s", err)

    async def async_save_current_day_temperature_extrema(self, extrema: Mapping[str, Any] | None) -> None:
        """Immediately persist the current-day extrema snapshot."""

        snapshot = dict(extrema) if extrema is not None else None
        if self._store is None:
            payload = dict(self._fallback_storage.get(self._entry_id, {}))
            if snapshot is None:
                payload.pop(const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA, None)
            else:
                payload[const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA] = snapshot
            self._fallback_storage[self._entry_id] = payload
            self._state_cache = dict(payload)
            return

        if snapshot is None:
            self._state_cache.pop(const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA, None)
        else:
            self._state_cache[const.STORAGE_KEY_CURRENT_DAY_TEMPERATURE_EXTREMA] = snapshot

        try:
            await self._store.async_save(self._build_save_payload())
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
