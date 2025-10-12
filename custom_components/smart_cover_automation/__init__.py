"""
Custom integration to smartly automate window covers with Home Assistant.

For more details about this integration, please refer to
https://github.com/helgeklein/ha-smart_cover_automation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .config import ConfKeys
from .config_flow import OptionsFlowHandler
from .const import DOMAIN, HA_OPTIONS, INTEGRATION_NAME, LOGGER
from .coordinator import DataUpdateCoordinator
from .data import RuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationConfigEntry

# List of platforms provided by this integration
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
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

        # Store the merged config in the coordinator for comparison during reload
        coordinator._merged_config = merged_config

        # Store shared state
        entry.runtime_data = RuntimeData(
            integration=async_get_loaded_integration(hass, entry.domain),
            coordinator=coordinator,
            config=merged_config,
        )

        # Call each platform's async_setup_entry()
        LOGGER.debug(f"Setting up platforms: {PLATFORMS}")
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Trigger initial coordinator refresh after platforms are set up
        # This ensures all entities are registered before the first state update
        LOGGER.debug("Starting initial coordinator refresh")
        await coordinator.async_config_entry_first_refresh()

        # Register the update listener
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
    """Reload config entry or just refresh coordinator based on what changed.

    For runtime options that have corresponding entities (switches, numbers),
    we only need to refresh the coordinator. For structural changes, we need a full reload.
    """
    # These keys can be changed at runtime via their corresponding entities
    # without requiring a full reload
    runtime_configurable_keys = {
        ConfKeys.ENABLED.value,
        ConfKeys.SIMULATION_MODE.value,
        ConfKeys.VERBOSE_LOGGING.value,
        ConfKeys.TEMP_THRESHOLD.value,
    }

    if hasattr(entry, "runtime_data") and entry.runtime_data:
        coordinator = entry.runtime_data.coordinator

        # Get the old configuration that the coordinator was using
        old_config = coordinator._merged_config

        # Get the new configuration from the updated entry
        new_config = {
            **dict(entry.data),
            **dict(getattr(entry, HA_OPTIONS, {}) or {}),
        }

        # Determine which keys have actually changed
        changed_keys = {key for key in set(old_config.keys()) | set(new_config.keys()) if old_config.get(key) != new_config.get(key)}

        # If the only changes are to runtime-configurable keys, just refresh
        if changed_keys and changed_keys.issubset(runtime_configurable_keys):
            LOGGER.debug(
                "Runtime-only option change detected (%s), refreshing coordinator",
                ", ".join(sorted(changed_keys)),
            )
            # Update the stored config with new values
            coordinator._merged_config = new_config
            entry.runtime_data.config = new_config
            # Trigger a coordinator refresh to apply the changes
            await coordinator.async_request_refresh()
            return

    # For all other changes (structural, new keys, etc.), do a full reload
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
