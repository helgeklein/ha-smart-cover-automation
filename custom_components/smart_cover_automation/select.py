"""Select platform for smart_cover_automation.

This module provides select entities that allow users to configure various
option/select settings of the Smart Cover Automation integration.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory

from . import const
from .const import SELECT_KEY_AUTOMATIC_REOPENING_MODE, SELECT_KEY_HEAT_PROTECTION_MODE, SELECT_KEY_LOCK_MODE
from .entity import IntegrationEntity
from .log import Log

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


#
# async_setup_entry
#
async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers all number entities for the integration.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    coordinator = entry.runtime_data.coordinator

    # Create all select entities
    entities = [
        LockModeSelect(coordinator),
        AutomaticReopeningModeSelect(coordinator),
        HeatProtectionModeSelect(coordinator),
    ]

    async_add_entities(entities)


#
# IntegrationSelect
#
class IntegrationSelect(IntegrationEntity, SelectEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base select entity for Smart Cover Automation integration.

    This abstract base class provides common functionality for all number
    entities in the integration. It handles the basic entity setup and provides
    a foundation for specific select implementations.

    The class provides:
    - Integration with the coordinator for data updates
    - Automatic availability tracking based on coordinator status
    - Consistent entity naming and identification patterns
    - Integration with Home Assistant's select platform
    - Base methods for persisting select value changes in config options
    """

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize the sensor entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                         and provides data for this select
            entity_description: Configuration describing the entity's properties
                                (name, device class, etc.)
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this sensor's characteristics
        self.entity_description = entity_description

        # Override the unique ID or HA uses the device class instead of the key.
        # Expected resulting entity_id pattern:
        #   sensor.smart_cover_automation_{translated_key}
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"


class EnumConfigSelect(IntegrationSelect):
    """Base select entity backed by a coordinator enum setting."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        *,
        key: str,
        icon: str,
        enum_type: type[StrEnum],
        coordinator_property: str,
        coordinator_setter: str,
        invalid_value_label: str,
    ) -> None:
        super().__init__(
            coordinator,
            SelectEntityDescription(
                key=key,
                translation_key=key,
                icon=icon,
                entity_category=EntityCategory.CONFIG,
            ),
        )

        self._attr_options = [mode.value for mode in enum_type]
        self._enum_type = enum_type
        self._coordinator_property = coordinator_property
        self._coordinator_setter = coordinator_setter
        self._invalid_value_label = invalid_value_label
        self._logger = Log(entry_id=coordinator.config_entry.entry_id)

    @property
    def current_option(self) -> str | None:  # pyright: ignore
        """Return the current selected option."""

        return getattr(self.coordinator, self._coordinator_property)

    async def async_select_option(self, option: str) -> None:
        """Persist a new option through the coordinator."""

        try:
            enum_value = self._enum_type(option)
        except ValueError:
            self._logger.error(f"Invalid {self._invalid_value_label} value: {option}")
            return

        coordinator_setter = getattr(self.coordinator, self._coordinator_setter)
        await coordinator_setter(enum_value)


class LockModeSelect(EnumConfigSelect):
    """Select entity for choosing lock mode."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(
            coordinator,
            key=SELECT_KEY_LOCK_MODE,
            icon="mdi:lock",
            enum_type=const.LockMode,
            coordinator_property="lock_mode",
            coordinator_setter="async_set_lock_mode",
            invalid_value_label="lock mode",
        )


class AutomaticReopeningModeSelect(EnumConfigSelect):
    """Select entity for choosing the automatic reopening mode."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(
            coordinator,
            key=SELECT_KEY_AUTOMATIC_REOPENING_MODE,
            icon="mdi:blinds-open",
            enum_type=const.ReopeningMode,
            coordinator_property="automatic_reopening_mode",
            coordinator_setter="async_set_automatic_reopening_mode",
            invalid_value_label="automatic reopening mode",
        )


class HeatProtectionModeSelect(EnumConfigSelect):
    """Select entity for choosing the heat protection mode."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(
            coordinator,
            key=SELECT_KEY_HEAT_PROTECTION_MODE,
            icon="mdi:white-balance-sunny",
            enum_type=const.HeatProtectionMode,
            coordinator_property="heat_protection_mode",
            coordinator_setter="async_set_heat_protection_mode",
            invalid_value_label="heat protection mode",
        )
