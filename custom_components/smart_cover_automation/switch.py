"""Switch platform for smart_cover_automation.

This module provides switch entities that control various aspects of the
Smart Cover Automation integration. The switches allow users to control
the automation behavior through the Home Assistant interface.

The switches that appear in Home Assistant are:
- Entity: switch.smart_cover_automation_enabled - Master automation enable/disable
- Entity: switch.smart_cover_automation_simulation_mode - Simulation mode control
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory

from .config import ConfKeys, resolve_entry
from .const import SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL
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
    """Set up the switch platform for the integration.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers all switch entities for the integration.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    coordinator = entry.runtime_data.coordinator

    # Create all switch entities
    entities = [
        # Master automation enable/disable switch
        EnabledSwitch(coordinator),
        # Simulation mode control switch
        SimulationModeSwitch(coordinator),
        # Verbose logging control switch
        VerboseLoggingSwitch(coordinator),
        # Weather sunny external control switch (disabled by default)
        WeatherSunnyExternalControlSwitch(coordinator),
    ]

    async_add_entities(entities)


#
# IntegrationSwitch
#
class IntegrationSwitch(IntegrationEntity, SwitchEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base switch entity for Smart Cover Automation integration.

    This abstract base class provides common functionality for all switch
    entities in the integration. It handles the basic entity setup and provides
    a foundation for specific switch implementations.

    The class provides:
    - Integration with the coordinator for data updates
    - Automatic availability tracking based on coordinator status
    - Consistent entity naming and identification patterns
    - Integration with Home Assistant's switch platform
    - Base methods for persisting switch state changes in config options
    """

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
        config_key: str,
    ) -> None:
        """Initialize the switch entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this switch
            entity_description: Configuration describing the entity's properties
                               (name, icon, etc.)
            config_key: The configuration key this switch controls
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this switch's characteristics
        self.entity_description = entity_description

        # Store the config key this switch controls
        self._config_key = config_key

        # Set unique ID to ensure proper device grouping and entity identification
        # This will result in entity_id: switch.smart_cover_automation_{translation_key}
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"

    # Note: We inherit the 'available' property from IntegrationEntity/CoordinatorEntity
    # which provides the correct coordinator-based availability logic.
    # No override is needed since the default behavior is exactly what we want.

    #
    # is_on
    #
    @property
    def is_on(self) -> bool:  # pyright: ignore
        """Return whether the switch is currently on.

        Reads from the resolved settings to get the current state.
        This reflects changes made through the integration's options flow.
        """
        resolved = resolve_entry(self.coordinator.config_entry)
        return bool(getattr(resolved, self._config_key.lower()))

    #
    # async_turn_on
    #
    async def async_turn_on(self, **_: Any) -> None:
        """Turn the switch on.

        Sets the config value to True and triggers a coordinator refresh
        to immediately apply the new setting.
        """
        await self._async_persist_option(self._config_key, True)

    #
    # async_turn_off
    #
    async def async_turn_off(self, **_: Any) -> None:
        """Turn the switch off.

        Sets the config value to False and triggers a coordinator refresh
        to immediately apply the new setting.
        """
        await self._async_persist_option(self._config_key, False)

    #
    # _async_persist_option
    #
    async def _async_persist_option(self, config_key: str, value: bool) -> None:
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


#
# EnabledSwitch
#
class EnabledSwitch(IntegrationSwitch):
    """Switch for controlling the master automation enable/disable state."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the automation enable/disable switch.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this switch
        """
        entity_description = SwitchEntityDescription(
            key=ConfKeys.ENABLED.value,
            translation_key=ConfKeys.ENABLED.value,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:toggle-switch-outline",
        )
        super().__init__(coordinator, entity_description, ConfKeys.ENABLED.value)


#
# SimulationModeSwitch
#
class SimulationModeSwitch(IntegrationSwitch):
    """Switch for controlling simulation mode."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Set the switch properties."""
        entity_description = SwitchEntityDescription(
            key=ConfKeys.SIMULATION_MODE.value,
            translation_key=ConfKeys.SIMULATION_MODE.value,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:play-circle-outline",
        )
        super().__init__(coordinator, entity_description, ConfKeys.SIMULATION_MODE.value)


#
# VerboseLoggingSwitch
#
class VerboseLoggingSwitch(IntegrationSwitch):
    """Switch for controlling verbose (debug) logging."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Set the switch properties."""
        entity_description = SwitchEntityDescription(
            key=ConfKeys.VERBOSE_LOGGING.value,
            translation_key=ConfKeys.VERBOSE_LOGGING.value,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:list-status",
        )
        super().__init__(coordinator, entity_description, ConfKeys.VERBOSE_LOGGING.value)

    @property
    def is_on(self) -> bool:  # pyright: ignore
        """Return whether verbose logging is enabled.

        Checks both the integration config and Home Assistant's logger level.
        Returns True if either:
        - The integration's verbose_logging config option is True
        - Home Assistant's logger is set to DEBUG level for this integration

        This allows the switch to reflect the actual logging state even when
        configured via configuration.yaml logger settings.
        """
        # Check if HA's logger is set to DEBUG for this integration
        logger = logging.getLogger("custom_components.smart_cover_automation")
        ha_logger_is_debug = logger.isEnabledFor(logging.DEBUG)

        # Check integration config
        resolved = resolve_entry(self.coordinator.config_entry)
        config_value = bool(getattr(resolved, self._config_key.lower()))

        # Return true if either is enabled
        return ha_logger_is_debug or config_value


#
# WeatherSunnyExternalControlSwitch
#
class WeatherSunnyExternalControlSwitch(IntegrationEntity, SwitchEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Switch for overriding the integration's weather sunny detection.

    This switch allows external sunlight sensors (e.g., pyranometers) to
    control the integration's "sun is shining" state, superseding the
    built-in weather forecast logic.

    The switch is disabled by default in the entity registry. When a user
    enables it, the override becomes active:
    - ON: Override sunny = True (sun is shining)
    - OFF: Override sunny = False (sun is not shining)

    When the entity is disabled again, the override is removed and the
    integration reverts to its built-in weather forecast logic.

    This switch is handled outside the standard _ConfSpec system because
    it requires tri-state semantics (absent / True / False) that the
    boolean-only spec system does not support.
    """

    # Disabled by default — users opt in by enabling the entity
    _attr_entity_registry_enabled_default = False

    #
    # __init__
    #
    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the weather sunny external control switch.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this switch
        """

        super().__init__(coordinator)

        self.entity_description = SwitchEntityDescription(
            key=SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL,
            translation_key=SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:weather-sunny-alert",
        )

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL}"

    #
    # async_added_to_hass
    #
    async def async_added_to_hass(self) -> None:
        """Persist the initial override state when the entity is first enabled.

        When a user enables this entity in the entity registry, the
        automation engine must immediately see the override key in the
        config options.  Without this, the key is absent and the engine
        falls back to the weather forecast logic, ignoring the switch.

        Only writes when the key is absent to avoid unnecessary config
        updates on regular restarts / reloads.
        """

        await super().async_added_to_hass()
        options: dict[str, Any] = dict(self.coordinator.config_entry.options or {})
        if SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL not in options:
            # First time the entity is enabled — seed the default (False)
            # so the engine sees the key on the very next coordinator refresh.
            await self._async_persist_override(False)

    #
    # is_on
    #
    @property
    def is_on(self) -> bool:  # pyright: ignore
        """Return whether the switch is set to sunny.

        Reads directly from config options since this setting is not
        part of the standard ResolvedConfig system.
        """

        options: Any = self.coordinator.config_entry.options or {}
        return bool(options.get(SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL, False))

    #
    # async_turn_on
    #
    async def async_turn_on(self, **_: Any) -> None:
        """Turn the switch on (sunny)."""

        await self._async_persist_override(True)

    #
    # async_turn_off
    #
    async def async_turn_off(self, **_: Any) -> None:
        """Turn the switch off (not sunny)."""

        await self._async_persist_override(False)

    #
    # async_will_remove_from_hass
    #
    async def async_will_remove_from_hass(self) -> None:
        """Clean up when the entity is removed or disabled.

        Removes the external control key from config options so the automation
        engine reverts to the built-in weather forecast logic.
        """

        entry = self.coordinator.config_entry
        current_options = dict(entry.options or {})
        if SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL in current_options:
            del current_options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL]
            self.coordinator.hass.config_entries.async_update_entry(entry, options=current_options)

    #
    # _async_persist_override
    #
    async def _async_persist_override(self, value: bool) -> None:
        """Persist the external control value to config options.

        Args:
            value: True for sunny, False for not sunny
        """

        entry = self.coordinator.config_entry
        current_options = dict(entry.options or {})
        current_options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] = value
        self.coordinator.hass.config_entries.async_update_entry(entry, options=current_options)
