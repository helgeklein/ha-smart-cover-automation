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
from .const import DOMAIN, HA_OPTIONS, INTEGRATION_NAME, LOGGER
from .coordinator import DataUpdateCoordinator
from .data import RuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationConfigEntry

# List of platforms provided by this integration
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,  # For automation status
    Platform.SWITCH,  # For enabling/disabling automation
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> bool:
    """Main init function to set up the integration.

    This function is called by Home Assistant during:
    - Initial setup of the integration via the UI (after the user completes the config flow)
    - Integration reload (via UI or when config options change)
    - HA restart

    What this function does:
    - Creates the coordinator
    - Merges config + options
    - Stores runtime data on the entry
    - Starts the coordinator
    - Sets up platforms
    - Sets up the reload listener
    """
    LOGGER.info(f"Setting up {INTEGRATION_NAME} integration")

    try:
        # Create the coordinator
        coordinator = DataUpdateCoordinator(hass, entry)

        # Merge config entry data with options (options override data)
        merged_config = {
            **dict(entry.data),
            **dict(getattr(entry, HA_OPTIONS, {}) or {}),
        }

        # Store shared state
        entry.runtime_data = RuntimeData(
            integration=async_get_loaded_integration(hass, entry.domain),
            coordinator=coordinator,
            config=merged_config,
        )

        # Trigger a call to the coordinator's _async_update_data()
        LOGGER.debug("Starting initial coordinator refresh")
        await coordinator.async_config_entry_first_refresh()

        # Call each platform's async_setup_entry()
        LOGGER.debug(f"Setting up platforms: {PLATFORMS}")
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    except (OSError, ValueError, TypeError) as err:
        # "Expected" errors: only log an error message
        LOGGER.error(f"Failed to set up {INTEGRATION_NAME} integration: {err}")
        return False
    except (ImportError, AttributeError, KeyError) as err:
        # "Unexpected" errors: log exception with stack trace
        LOGGER.exception(f"Error during {INTEGRATION_NAME} setup: {err}")
        return False
    except Exception as err:
        # "Unexpected" errors: log exception with stack trace
        LOGGER.exception(f"Error during {INTEGRATION_NAME} setup: {err}")
        return False
    else:
        LOGGER.info(f"{INTEGRATION_NAME} integration setup completed")
        return True


async def async_get_options_flow(entry: IntegrationConfigEntry) -> OptionsFlowHandler:
    """Return the options flow for this handler.

    This function is called by Home Assistant when:
    - The user clicks the gear icon to bring up the integration's options dialog.
    """
    return OptionsFlowHandler(entry)


async def async_unload_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    LOGGER.info(f"Unloading {INTEGRATION_NAME} integration")
    try:
        return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    except (OSError, ValueError, TypeError) as err:
        # "Expected" errors: only log an error message
        LOGGER.error(f"Error unloading {INTEGRATION_NAME} integration: {err}")
        return False
    except Exception as err:
        # "Unexpected" errors: log exception with stack trace
        LOGGER.exception(f"Error unloading {INTEGRATION_NAME} integration: {err}")
        return False


async def async_reload_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> None:
    """Reload config entry."""
    LOGGER.info(f"Reloading {INTEGRATION_NAME} integration")
    await hass.config_entries.async_reload(entry.entry_id)


# Re-export common package-level symbols for convenience imports in tooling/tests
__all__ = [
    "DOMAIN",
    "PLATFORMS",
    "async_setup_entry",
    "async_unload_entry",
    "async_reload_entry",
]
