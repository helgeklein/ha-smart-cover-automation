"""Switch platform for smart_cover_automation.

Provides a Home Assistant switch entity that controls whether the smart cover automation
is enabled or disabled. This switch:

- Represents the global enabled/disabled state of the automation
- Persists its state in the integration's options (configuration)
- Triggers coordinator refresh when toggled to immediately apply state changes
- Inherits availability from the coordinator status

The switch state is stored in the config entry options, allowing it to persist
across Home Assistant restarts and integration reloads.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from custom_components.smart_cover_automation.const import HA_OPTIONS

from .config import ConfKeys, resolve_entry
from .const import SWITCH_KEY_ENABLED
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
    It creates and registers the automation control switch.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    # Create the automation control switch
    entity_description = SwitchEntityDescription(
        key=SWITCH_KEY_ENABLED,
        icon="mdi:toggle-switch-outline",
        translation_key=SWITCH_KEY_ENABLED,
    )

    async_add_entities(
        [
            IntegrationSwitch(
                coordinator=entry.runtime_data.coordinator,
                entity_description=entity_description,
            )
        ]
    )


class IntegrationSwitch(IntegrationEntity, SwitchEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Smart cover automation master enable/disable switch.

    This switch controls the global enabled state of the automation system.
    When turned off, the automation stops processing temperature and sun data
    and will not move any covers. When turned on, normal automation resumes.

    The switch state is persisted in the integration's configuration options,
    ensuring it survives Home Assistant restarts. State changes trigger an
    immediate coordinator refresh to apply the new setting.

    Inherits device grouping from IntegrationEntity and availability status
    from CoordinatorEntity via the inheritance chain.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the automation control switch.

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
        # This will result in entity_id: switch.smart_cover_automation_enabled
        self._attr_unique_id = f"smart_cover_automation_{entity_description.key}"

    # Note: We inherit the 'available' property from IntegrationEntity/CoordinatorEntity
    # which provides the correct coordinator-based availability logic.
    # No override is needed since the default behavior is exactly what we want.

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
        # Persist enabled=True in options if available
        entry = self.coordinator.config_entry
        current = dict(getattr(entry, HA_OPTIONS, {}) or {})
        current[ConfKeys.ENABLED.value] = True
        await entry.async_set_options(current)  # type: ignore[attr-defined]
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Disable the smart cover automation.

        Sets the enabled flag to False in the integration's options and triggers
        a coordinator refresh to immediately stop automation processing.
        The state change persists across Home Assistant restarts.
        """
        entry = self.coordinator.config_entry
        current = dict(getattr(entry, HA_OPTIONS, {}) or {})
        current[ConfKeys.ENABLED.value] = False
        await entry.async_set_options(current)  # type: ignore[attr-defined]
        await self.coordinator.async_request_refresh()
