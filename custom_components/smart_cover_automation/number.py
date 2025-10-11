"""Number platform for smart_cover_automation.

This module provides number entities that allow users to adjust numeric
configuration values for the Smart Cover Automation integration through
the Home Assistant interface.

The number entities that appear in Home Assistant are:
- Entity: number.smart_cover_automation_temp_threshold - Temperature threshold control
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature

from .config import ConfKeys, resolve_entry
from .const import DOMAIN
from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform for the integration.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers all number entities for the integration.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    coordinator = entry.runtime_data.coordinator

    # Create all number entities
    entities = [
        # Temperature threshold control
        TempThresholdNumber(coordinator),
    ]

    async_add_entities(entities)


class IntegrationNumber(IntegrationEntity, NumberEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base number entity for Smart Cover Automation integration.

    This abstract base class provides common functionality for all number
    entities in the integration. It handles the basic entity setup and provides
    a foundation for specific number implementations.

    The class provides:
    - Integration with the coordinator for data updates
    - Automatic availability tracking based on coordinator status
    - Consistent entity naming and identification patterns
    - Integration with Home Assistant's number platform
    - Base methods for persisting number value changes in config options
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: NumberEntityDescription,
        config_key: str,
    ) -> None:
        """Initialize the number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number
            entity_description: Configuration describing the entity's properties
                               (name, icon, unit, etc.)
            config_key: The configuration key this number controls
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this number's characteristics
        self.entity_description = entity_description

        # Store the config key this number controls
        self._config_key = config_key

        # Set unique ID to ensure proper device grouping and entity identification
        # This will result in entity_id: number.smart_cover_automation_{translation_key}
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"

    @property
    def native_value(self) -> float | None:  # pyright: ignore
        """Return the current value of the number.

        Reads from the resolved settings to get the current value.
        This reflects changes made through the integration's options flow.
        """
        resolved = resolve_entry(self.coordinator.config_entry)
        return float(getattr(resolved, self._config_key.lower()))

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value.

        Updates the config value and triggers a coordinator refresh
        to immediately apply the new setting.

        Args:
            value: The new numeric value to set
        """
        await self._async_persist_option(self._config_key, value)

    async def _async_persist_option(self, config_key: str, value: float) -> None:
        """Persist an option to the config entry.

        This method updates the integration's configuration options. The update
        will trigger the smart reload listener in __init__.py, which will
        intelligently decide whether to do a full reload or just refresh the
        coordinator based on which keys changed.

        Args:
            config_key: The configuration key to update.
            value: The new value for the key.
        """
        entry = self.coordinator.config_entry
        current_options = dict(entry.options or {})
        current_options[config_key] = value

        # This will trigger the update listener (async_reload_entry) in __init__.py
        # which will compare configs and decide on refresh vs. reload
        self.coordinator.hass.config_entries.async_update_entry(entry, options=current_options)


class TempThresholdNumber(IntegrationNumber):
    """Number entity for controlling the temperature threshold."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the temperature threshold number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number
        """
        entity_description = NumberEntityDescription(
            key="temp_threshold",
            icon="mdi:thermometer",
            translation_key="temp_threshold",
            entity_category=EntityCategory.CONFIG,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            native_min_value=10.0,
            native_max_value=40.0,
            native_step=0.5,
            mode=NumberMode.BOX,
        )
        super().__init__(coordinator, entity_description, ConfKeys.TEMP_THRESHOLD.value)
