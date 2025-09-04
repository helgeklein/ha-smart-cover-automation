"""
Custom integration to smartly automate window covers with Home Assistant.

For more details about this integration, please refer to
https://github.com/helgeklein/ha-smart_cover_automation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .config_flow import OptionsFlowHandler
from .const import DOMAIN, LOGGER
from .coordinator import DataUpdateCoordinator
from .data import IntegrationData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,  # For automation status
    Platform.SWITCH,  # For enabling/disabling automation
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> bool:
    """Set up this integration using the UI."""
    LOGGER.info("Setting up Smart Cover Automation integration")

    try:
        coordinator = DataUpdateCoordinator(hass, entry)

        # Merge config entry data with options (options override data)
        merged_config = {
            **dict(entry.data),
            **dict(getattr(entry, "options", {}) or {}),
        }

        entry.runtime_data = IntegrationData(
            integration=async_get_loaded_integration(hass, entry.domain),
            coordinator=coordinator,
            config=merged_config,
        )

        LOGGER.debug("Starting initial coordinator refresh")
        # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
        await coordinator.async_config_entry_first_refresh()

        LOGGER.debug("Setting up platforms: %s", PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    except (OSError, ValueError, TypeError) as err:
        LOGGER.error(
            "Failed to set up Smart Cover Automation integration: %s",
            err,
        )
        return False
    except (ImportError, AttributeError, KeyError) as err:
        LOGGER.exception(
            "Configuration error during Smart Cover Automation setup: %s",
            err,
        )
        return False
    else:
        LOGGER.info("Smart Cover Automation integration setup completed")
        return True


async def async_get_options_flow(entry: IntegrationConfigEntry) -> OptionsFlowHandler:
    """Return the options flow for this handler."""
    return OptionsFlowHandler(entry)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    LOGGER.info("Unloading Smart Cover Automation integration")
    try:
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except (OSError, ValueError, TypeError) as err:
        LOGGER.error(
            "Error unloading Smart Cover Automation integration: %s",
            err,
        )
        return False


async def async_reload_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> None:
    """Reload config entry."""
    LOGGER.info("Reloading Smart Cover Automation integration")
    await hass.config_entries.async_reload(entry.entry_id)


# Re-export common package-level symbols for convenience imports in tooling/tests
__all__ = [
    "DOMAIN",
    "PLATFORMS",
    "async_setup_entry",
    "async_unload_entry",
    "async_reload_entry",
]
