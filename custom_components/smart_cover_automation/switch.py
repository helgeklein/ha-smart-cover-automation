"""Switch platform for smart_cover_automation.

This module provides switch entities that control various aspects of the
Smart Cover Automation integration. The switches allow users to control
the automation behavior through the Home Assistant interface.

The switches that appear in Home Assistant are:
- Entity: switch.smart_cover_automation_enabled - Master automation enable/disable
- Entity: switch.smart_cover_automation_simulation_mode - Simulation mode control
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from custom_components.smart_cover_automation.const import HA_OPTIONS

from .config import ConfKeys, resolve_entry
from .const import SWITCH_KEY_ENABLED, SWITCH_KEY_SIMULATION_MODE
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
    ]

    async_add_entities(entities)


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

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this switch
            entity_description: Configuration describing the entity's properties
                               (name, icon, etc.)
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this switch's characteristics
        self.entity_description = entity_description

        # Set unique ID to ensure proper device grouping and entity identification
        # This will result in entity_id: switch.smart_cover_automation_{translation_key}
        self._attr_unique_id = f"smart_cover_automation_{entity_description.key}"

    # Note: We inherit the 'available' property from IntegrationEntity/CoordinatorEntity
    # which provides the correct coordinator-based availability logic.
    # No override is needed since the default behavior is exactly what we want.

    async def _persist_option_and_refresh(self, config_key: str, value: bool) -> None:
        """Persist a configuration option and trigger coordinator refresh.

        This helper method handles the common pattern of updating a configuration
        option in the integration's stored options and then requesting a coordinator
        refresh to apply the change immediately.

        Args:
            config_key: The configuration key to update in the options
            value: The boolean value to set for the configuration key
        """
        entry = self.coordinator.config_entry
        current = dict(getattr(entry, HA_OPTIONS, {}) or {})
        current[config_key] = value
        await entry.async_set_options(current)  # type: ignore[attr-defined]
        await self.coordinator.async_request_refresh()


class EnabledSwitch(IntegrationSwitch):
    """Switch for controlling the master automation enable/disable state.

    This switch controls the global enabled state of the automation system.
    When turned off, the automation stops processing temperature and sun data
    and will not move any covers. When turned on, normal automation resumes.

    The switch state is persisted in the integration's configuration options,
    ensuring it survives Home Assistant restarts. State changes trigger an
    immediate coordinator refresh to apply the new setting.

    Inherits device grouping from IntegrationEntity and availability status
    from CoordinatorEntity via the inheritance chain.
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the automation enable/disable switch.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this switch
        """
        entity_description = SwitchEntityDescription(
            key=SWITCH_KEY_ENABLED,
            icon="mdi:toggle-switch-outline",
            translation_key=SWITCH_KEY_ENABLED,
        )
        super().__init__(coordinator, entity_description)

    @cached_property
    def is_on(self) -> bool:
        """Return whether the automation is currently enabled.

        Reads from the resolved settings to get the current enabled state.
        This reflects changes made through the integration's options flow.
        """
        resolved = resolve_entry(self.coordinator.config_entry)
        return resolved.enabled

    async def async_turn_on(self, **_: Any) -> None:
        """Enable the smart cover automation.

        Sets the enabled flag to True in the integration's options and triggers
        a coordinator refresh to immediately start automation processing.
        The state change persists across Home Assistant restarts.
        """
        await self._persist_option_and_refresh(ConfKeys.ENABLED.value, True)

    async def async_turn_off(self, **_: Any) -> None:
        """Disable the smart cover automation.

        Sets the enabled flag to False in the integration's options and triggers
        a coordinator refresh to immediately stop automation processing.
        The state change persists across Home Assistant restarts.
        """
        await self._persist_option_and_refresh(ConfKeys.ENABLED.value, False)


class SimulationModeSwitch(IntegrationSwitch):
    """Switch for controlling simulation mode.

    This switch controls whether the automation runs in simulation mode.
    When simulation mode is enabled, the automation performs all calculations
    and decision-making but doesn't actually send commands to move covers.

    This is useful for:
    - Testing automation logic without affecting physical covers
    - Monitoring what the automation would do in different conditions
    - Development and troubleshooting

    The switch state is persisted in the integration's configuration options,
    ensuring it survives Home Assistant restarts. State changes trigger an
    immediate coordinator refresh to apply the new setting.
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the simulation mode switch.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this switch
        """
        entity_description = SwitchEntityDescription(
            key=SWITCH_KEY_SIMULATION_MODE,
            icon="mdi:play-circle-outline",
            translation_key=SWITCH_KEY_SIMULATION_MODE,
        )
        super().__init__(coordinator, entity_description)

    @cached_property
    def is_on(self) -> bool:
        """Return whether simulation mode is currently enabled.

        Reads from the resolved settings to get the current simulation state.
        This reflects changes made through the integration's options flow.
        """
        resolved = resolve_entry(self.coordinator.config_entry)
        return resolved.simulating

    async def async_turn_on(self, **_: Any) -> None:
        """Enable simulation mode.

        Sets the simulating flag to True in the integration's options and triggers
        a coordinator refresh to immediately apply simulation mode. The automation
        will continue to run but won't move any covers.
        """
        await self._persist_option_and_refresh(ConfKeys.SIMULATING.value, True)

    async def async_turn_off(self, **_: Any) -> None:
        """Disable simulation mode.

        Sets the simulating flag to False in the integration's options and triggers
        a coordinator refresh to immediately disable simulation mode. The automation
        will resume normal operation and can move covers as designed.
        """
        await self._persist_option_and_refresh(ConfKeys.SIMULATING.value, False)
