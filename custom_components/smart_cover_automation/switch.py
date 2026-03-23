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
from .const import (
    COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL,
    SWITCH_KEY_COVER_WEATHER_HOT_EXTERNAL_CONTROL,
    SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL,
    SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL,
)
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
    resolved = resolve_entry(entry)

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
        # Weather hot external control switch (disabled by default)
        WeatherHotExternalControlSwitch(coordinator),
    ]

    entities.extend(CoverWeatherHotExternalControlSwitch(coordinator, cover_entity_id) for cover_entity_id in resolved.covers)

    async_add_entities(entities)


#
# _format_cover_name
#
def _format_cover_name(coordinator: DataUpdateCoordinator, cover_entity_id: str) -> str:
    """Return a human-friendly name for a cover entity.

    Uses the current state friendly name when available. Falls back to a title-
    cased object ID so names remain readable during startup or in unit tests.

    Args:
        coordinator: Coordinator providing access to Home Assistant state.
        cover_entity_id: Entity ID of the cover.

    Returns:
        Human-friendly cover name.
    """

    state = coordinator.hass.states.get(cover_entity_id)
    if state is not None:
        friendly_name = state.attributes.get("friendly_name")
        if isinstance(friendly_name, str) and friendly_name.strip():
            return friendly_name.strip()

    object_id = cover_entity_id.split(".", 1)[-1]
    return object_id.replace("_", " ").strip().title()


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
# TriStateExternalControlSwitch
#
class TriStateExternalControlSwitch(IntegrationEntity, SwitchEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base class for disabled-by-default tri-state external control switches.

    The switch state is persisted directly in config entry options:
    - key absent: external control disabled
    - key present with True: force True
    - key present with False: force False
    """

    _attr_entity_registry_enabled_default = False

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        *,
        config_key: str,
        translation_key: str,
        icon: str,
        name: str | None = None,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize the tri-state external control switch.

        Args:
            coordinator: The DataUpdateCoordinator managing this entry.
            config_key: Raw config key to persist in entry options.
            translation_key: Translation key used for the entity description.
            icon: Icon shown in Home Assistant.
            name: Optional explicit entity name.
            translation_placeholders: Optional placeholders used by Home
                Assistant when rendering the translated entity name.
        """

        super().__init__(coordinator)

        self._config_key = config_key
        self.entity_description = SwitchEntityDescription(
            key=config_key,
            translation_key=translation_key,
            entity_category=EntityCategory.CONFIG,
            icon=icon,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{config_key}"
        if name is not None:
            self._attr_name = name
        if translation_placeholders is not None:
            self._attr_translation_placeholders = translation_placeholders

    #
    # async_added_to_hass
    #
    async def async_added_to_hass(self) -> None:
        """Persist the initial override state when the entity is first enabled."""

        await super().async_added_to_hass()
        options: dict[str, Any] = dict(self.coordinator.config_entry.options or {})
        if self._config_key not in options:
            await self._async_persist_override(False)

    #
    # is_on
    #
    @property
    def is_on(self) -> bool:  # pyright: ignore
        """Return the persisted override state.

        Missing key means the entity is enabled in the registry but external
        control has not yet been persisted for this config entry.
        """

        options: Any = self.coordinator.config_entry.options or {}
        return bool(options.get(self._config_key, False))

    #
    # async_turn_on
    #
    async def async_turn_on(self, **_: Any) -> None:
        """Turn the switch on."""

        await self._async_persist_override(True)

    #
    # async_turn_off
    #
    async def async_turn_off(self, **_: Any) -> None:
        """Turn the switch off."""

        await self._async_persist_override(False)

    #
    # async_will_remove_from_hass
    #
    async def async_will_remove_from_hass(self) -> None:
        """Clean up the persisted override when the entity is disabled."""

        entry = self.coordinator.config_entry
        current_options = dict(entry.options or {})
        if self._config_key in current_options:
            del current_options[self._config_key]
            self.coordinator.hass.config_entries.async_update_entry(entry, options=current_options)

    #
    # _async_persist_override
    #
    async def _async_persist_override(self, value: bool) -> None:
        """Persist the external control value to config options.

        Args:
            value: True to force the controlled state on, False to force it off.
        """

        entry = self.coordinator.config_entry
        current_options = dict(entry.options or {})
        current_options[self._config_key] = value
        self.coordinator.hass.config_entries.async_update_entry(entry, options=current_options)


#
# WeatherSunnyExternalControlSwitch
#
class WeatherSunnyExternalControlSwitch(TriStateExternalControlSwitch):
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

    #
    # __init__
    #
    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the weather sunny external control switch.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this switch
        """

        super().__init__(
            coordinator,
            config_key=SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL,
            translation_key=SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL,
            icon="mdi:weather-sunny-alert",
        )


#
# WeatherHotExternalControlSwitch
#
class WeatherHotExternalControlSwitch(TriStateExternalControlSwitch):
    """Switch for overriding the integration's weather hot detection."""

    #
    # __init__
    #
    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the weather hot external control switch."""

        super().__init__(
            coordinator,
            config_key=SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL,
            translation_key=SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL,
            icon="mdi:thermometer-alert",
        )


#
# CoverWeatherHotExternalControlSwitch
#
class CoverWeatherHotExternalControlSwitch(TriStateExternalControlSwitch):
    """Per-cover switch for overriding hot-weather detection."""

    #
    # __init__
    #
    def __init__(self, coordinator: DataUpdateCoordinator, cover_entity_id: str) -> None:
        """Initialize the per-cover weather hot external control switch.

        Args:
            coordinator: Coordinator for the integration instance.
            cover_entity_id: Cover entity ID this switch applies to.
        """

        self._cover_entity_id = cover_entity_id
        cover_name = _format_cover_name(coordinator, cover_entity_id)
        config_key = f"{cover_entity_id}_{COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"
        super().__init__(
            coordinator,
            config_key=config_key,
            translation_key=SWITCH_KEY_COVER_WEATHER_HOT_EXTERNAL_CONTROL,
            icon="mdi:thermometer-chevron-up",
            translation_placeholders={"cover_name": cover_name},
        )
