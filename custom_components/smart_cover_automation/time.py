"""Time platform for smart_cover_automation.

This module provides time entities for configuration values that are supplied
externally at runtime.
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory

from .const import (
    TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME,
    TIME_KEY_MORNING_OPENING_EXTERNAL_TIME,
    EveningClosureMode,
    MorningOpeningMode,
)
from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


#
# async_setup_entry
#
async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the time platform for the integration."""

    coordinator = entry.runtime_data.coordinator
    resolved = coordinator._resolved_settings()

    entities: list[IntegrationTime] = []
    if resolved.evening_closure_mode == EveningClosureMode.EXTERNAL:
        entities.append(EveningClosureExternalTime(coordinator))
    if resolved.morning_opening_mode == MorningOpeningMode.EXTERNAL:
        entities.append(MorningOpeningExternalTime(coordinator))

    async_add_entities(entities)


#
# IntegrationTime
#
class IntegrationTime(IntegrationEntity, TimeEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base time entity for Smart Cover Automation integration."""

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: TimeEntityDescription,
        config_key: str,
    ) -> None:
        """Initialize the time entity."""

        super().__init__(coordinator)
        self.entity_description = entity_description
        self._config_key = config_key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"

    @property
    def native_value(self) -> time | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return the currently stored time value, if any."""

        options = dict(self.coordinator.config_entry.options or {})
        raw_value = options.get(self._config_key)
        if raw_value in (None, ""):
            return None

        from .config import _Converters

        try:
            return _Converters.to_time(raw_value)
        except AttributeError, TypeError, ValueError:
            return None

    async def async_set_value(self, value: time) -> None:
        """Persist a new time value."""

        entry = self.coordinator.config_entry
        current_options = dict(entry.options or {})
        current_options[self._config_key] = value.isoformat()
        self.coordinator.hass.config_entries.async_update_entry(entry, options=current_options)


#
# MorningOpeningExternalTime
#
class MorningOpeningExternalTime(IntegrationTime):
    """Global external morning opening time."""

    #
    # __init__
    #
    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the external morning opening time entity."""

        entity_description = TimeEntityDescription(
            key=TIME_KEY_MORNING_OPENING_EXTERNAL_TIME,
            translation_key=TIME_KEY_MORNING_OPENING_EXTERNAL_TIME,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:weather-sunset-up",
        )
        super().__init__(coordinator, entity_description, TIME_KEY_MORNING_OPENING_EXTERNAL_TIME)


#
# EveningClosureExternalTime
#
class EveningClosureExternalTime(IntegrationTime):
    """Global external evening closure time."""

    #
    # __init__
    #
    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the external evening closure time entity."""

        entity_description = TimeEntityDescription(
            key=TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME,
            translation_key=TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:weather-sunset-down",
        )
        super().__init__(coordinator, entity_description, TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME)
