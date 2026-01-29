"""
Custom integration to smartly automate window covers with Home Assistant.

For more details about this integration, please refer to
https://github.com/helgeklein/ha-smart_cover_automation
"""

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_loaded_integration

from . import const
from .config import ConfKeys, get_runtime_configurable_keys
from .config_flow import OptionsFlowHandler
from .const import (
    DATA_COORDINATORS,
    DOMAIN,
    HA_OPTIONS,
    INTEGRATION_NAME,
    LOGGER,
    SERVICE_FIELD_LOCK_MODE,
    SERVICE_LOGBOOK_ENTRY,
    SERVICE_SET_LOCK,
    TRANSL_LOGBOOK_REASON_HEAT_PROTECTION,
    TRANSL_LOGBOOK_VERB_OPENING,
)
from .coordinator import DataUpdateCoordinator
from .data import RuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationConfigEntry

# List of platforms provided by this integration
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


#
# _async_migrate_unique_ids
#
async def _async_migrate_unique_ids(hass: HomeAssistant, entry: IntegrationConfigEntry) -> None:
    """Migrate legacy unique IDs to the new format (entry_id based).

    Old format: {DOMAIN}_{key} (e.g. smart_cover_automation_status)
    New format: {entry_id}_{key} (e.g. 1a2b3c4d_status)

    This preserves the user-facing entity_id while allowing multiple instances.
    """
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)

    # Filter for entities that need migration to avoid unnecessary logging on every boot
    legacy_candidates = [entity for entity in entries if entity.unique_id.startswith(f"{const.DOMAIN}_")]

    if not legacy_candidates:
        return

    LOGGER.info(
        "Starting unique ID migration for entry %s. Found %d entities to migrate.",
        entry.entry_id,
        len(legacy_candidates),
    )

    migrated_count = 0
    for entity in legacy_candidates:
        old_unique_id = entity.unique_id
        # Extract key part
        key = old_unique_id.replace(f"{const.DOMAIN}_", "", 1)
        new_unique_id = f"{entry.entry_id}_{key}"

        LOGGER.info(f"Migrating entity {entity.entity_id} unique_id from {old_unique_id} to {new_unique_id}")
        try:
            registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
            migrated_count += 1
        except ValueError as err:
            # Collision detected. The new ID might be taken by an orphaned entity.
            # Derive domain from entity_id (safe way)
            entity_domain = entity.entity_id.split(".", 1)[0]

            # Check who owns the new unique_id
            existing_entity_id = registry.async_get_entity_id(entity_domain, entity.platform, new_unique_id)

            collision_resolved = False
            if existing_entity_id:
                LOGGER.warning(
                    "Collision detected while migrating %s to %s. Existing owner: %s",
                    entity.entity_id,
                    new_unique_id,
                    existing_entity_id,
                )
                existing_entry = registry.async_get(existing_entity_id)
                # If the blocking entity has no config entry connected, it's an orphan/zombie
                if existing_entry and existing_entry.config_entry_id is None:
                    LOGGER.warning(
                        "Found orphaned entity %s blocking migration to %s. Removing it.",
                        existing_entity_id,
                        new_unique_id,
                    )
                    registry.async_remove(existing_entity_id)
                    # Retry migration
                    try:
                        registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
                        migrated_count += 1
                        collision_resolved = True
                    except ValueError as retry_err:
                        LOGGER.error("Migration retry failed for %s: %s", entity.entity_id, retry_err)
            else:
                LOGGER.warning(
                    f"Collaboration collision detected for {entity.entity_id} but no blocking entity found in registry query: {err}"
                )

            if not collision_resolved:
                # If we get here, it's a real conflict we can't auto-resolve
                LOGGER.warning(f"Error migrating unique_id for {entity.entity_id}: {err}")
        except Exception as err:
            LOGGER.error(f"Unexpected error migrating {entity.entity_id}: {err}")

    LOGGER.info(f"Finished unique ID migration. Migrated {migrated_count} entities.")


#
# _async_register_lock_service
#
async def _async_register_lock_service(hass: HomeAssistant) -> None:
    """Register the set_lock service.

    Args:
        hass: Home Assistant instance
    """
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv
    from homeassistant.helpers import service

    #
    # async_handle_set_lock
    #
    async def async_handle_set_lock(call: ServiceCall) -> None:
        """Handle set_lock service call.

        Args:
            call: Service call with lock_mode parameter
        """
        lock_mode = call.data[SERVICE_FIELD_LOCK_MODE]

        # Extract target config entry IDs from the service call (if any)
        target_entry_ids = await service.async_extract_config_entry_ids(hass, call)

        LOGGER.info(f"Service call: set_lock(lock_mode={lock_mode}, targets={len(target_entry_ids)})")

        # Validate lock mode
        valid_modes = [mode.value for mode in const.LockMode]

        if lock_mode not in valid_modes:
            LOGGER.error(f"Invalid lock mode: {lock_mode}. Valid modes: {valid_modes}")
            raise ValueError(f"Invalid lock mode: {lock_mode}")

        # Resolve coordinators
        domain_data = hass.data.get(DOMAIN, {})
        coordinators = domain_data.get(DATA_COORDINATORS, {})

        if not coordinators:
            LOGGER.warning("Set lock service called but no coordinators are registered")
            return

        # Determine which coordinators to update
        if target_entry_ids:
            # Apply only to targeted instances
            target_coordinators = [coordinators[entry_id] for entry_id in target_entry_ids if entry_id in coordinators]
        else:
            # No target specified -> Apply to ALL instances (global broadcast)
            target_coordinators = list(coordinators.values())

        if not target_coordinators:
            LOGGER.warning(
                "Set lock service: No matching coordinators found for targets: %s",
                target_entry_ids,
            )
            return

        # Apply lock mode to all targeted coordinators
        for coordinator in target_coordinators:
            await coordinator.async_set_lock_mode(lock_mode)

    # Define service schema
    set_lock_schema = vol.Schema(
        {
            vol.Required(SERVICE_FIELD_LOCK_MODE): cv.string,
        }
    )

    # Register service (only if not already registered)
    if not hass.services.has_service(DOMAIN, SERVICE_SET_LOCK):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_LOCK,
            async_handle_set_lock,
            schema=set_lock_schema,
        )
        LOGGER.debug("Set lock service registered")


#
# _handle_logbook_entry_service
#
async def _handle_logbook_entry_service(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle service calls that create logbook entries.

    This service is registered once per Home Assistant instance and routes
    logbook entry requests to the appropriate coordinator based on:
    1. Explicit config_entry_id (if provided)
    2. Cover entity_id match
    3. First available coordinator (fallback)
    """
    domain_state = hass.data.get(DOMAIN) or {}
    registered_coordinators = domain_state.get(DATA_COORDINATORS, {})

    if not registered_coordinators:
        LOGGER.warning("Logbook service called but no coordinators are registered")
        return

    entity_id = call.data.get("entity_id")
    target_position = call.data.get("target_position")

    if entity_id is None or target_position is None:
        LOGGER.warning("Logbook service requires 'entity_id' and 'target_position'")
        return

    try:
        target_pos_int = int(target_position)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid target_position '%s' provided to logbook service", target_position)
        return

    verb_key = call.data.get("verb_key", TRANSL_LOGBOOK_VERB_OPENING)
    reason_key = call.data.get("reason_key", TRANSL_LOGBOOK_REASON_HEAT_PROTECTION)

    coordinator_for_call: DataUpdateCoordinator | None = None

    # Optional explicit config entry targeting
    config_entry_id = call.data.get("config_entry_id")
    if config_entry_id:
        coordinator_for_call = registered_coordinators.get(config_entry_id)

    # Try to match coordinator by cover entity if still unresolved
    if coordinator_for_call is None:
        for candidate in registered_coordinators.values():
            if candidate is None:
                continue
            covers = {} if candidate.data is None else candidate.data.covers
            if entity_id in covers:
                coordinator_for_call = candidate
                break

    # Fall back to the first available coordinator
    if coordinator_for_call is None:
        coordinator_for_call = next(iter(registered_coordinators.values()), None)

    if coordinator_for_call is None:
        LOGGER.warning("Logbook service could not locate an active coordinator")
        return

    await coordinator_for_call._ha_interface.add_logbook_entry(
        verb_key=verb_key,
        entity_id=entity_id,
        reason_key=reason_key,
        target_pos=target_pos_int,
    )


#
# async_setup_entry
#
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
    # Configure logging level early to capture setup/migration logs
    options = dict(getattr(entry, HA_OPTIONS, {}) or {})
    if options.get(ConfKeys.VERBOSE_LOGGING.value, False):
        LOGGER.setLevel(logging.DEBUG)
        LOGGER.debug("Verbose logging enabled by configuration (early setup)")

    LOGGER.info("Starting integration setup")

    # Migrate unique IDs if needed
    await _async_migrate_unique_ids(hass, entry)

    try:
        # Create the coordinator
        coordinator = DataUpdateCoordinator(hass, entry)

        # Get configuration from options (all user settings are stored in options)
        merged_config = dict(getattr(entry, HA_OPTIONS, {}) or {})

        # Store the config in the coordinator for comparison during reload
        coordinator._merged_config = merged_config

        # Store shared state
        entry.runtime_data = RuntimeData(
            integration=async_get_loaded_integration(hass, entry.domain),
            coordinator=coordinator,
            config=merged_config,
        )

        # Track coordinator references for service handling
        domain_data = hass.data.setdefault(DOMAIN, {})
        coordinators = domain_data.setdefault(DATA_COORDINATORS, {})
        coordinators[entry.entry_id] = coordinator

        # Register services once per hass instance
        if not hass.services.has_service(DOMAIN, SERVICE_LOGBOOK_ENTRY):
            hass.services.async_register(
                DOMAIN,
                SERVICE_LOGBOOK_ENTRY,
                partial(_handle_logbook_entry_service, hass),
            )

        # Register lock service
        await _async_register_lock_service(hass)

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


#
# async_get_options_flow
#
async def async_get_options_flow(entry: IntegrationConfigEntry) -> OptionsFlowHandler:
    """Return the options flow for this handler.

    This function is called by Home Assistant when:
    - The user clicks the gear icon to bring up the integration's options dialog.
    """
    return OptionsFlowHandler(entry)


#
# async_unload_entry
#
async def async_unload_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    LOGGER.info(f"Unloading {INTEGRATION_NAME} integration")
    try:
        result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

        domain_state = hass.data.get(DOMAIN)
        if domain_state and DATA_COORDINATORS in domain_state:
            coordinators: dict[str, DataUpdateCoordinator] = domain_state[DATA_COORDINATORS]
            coordinators.pop(entry.entry_id, None)

            if not coordinators:
                domain_state.pop(DATA_COORDINATORS, None)
                if not domain_state:
                    hass.data.pop(DOMAIN, None)
                if hass.services.has_service(DOMAIN, SERVICE_LOGBOOK_ENTRY):
                    hass.services.async_remove(DOMAIN, SERVICE_LOGBOOK_ENTRY)

        return result
    except (OSError, ValueError, TypeError) as err:
        # "Expected" errors: only log an error message
        LOGGER.error(f"Error unloading {INTEGRATION_NAME} integration: {err}")
        return False
    except Exception as err:
        # "Unexpected" errors: log exception with stack trace
        LOGGER.exception(f"Error unloading {INTEGRATION_NAME} integration: {err}")
        return False


#
# async_reload_entry
#
async def async_reload_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
) -> None:
    """Reload config entry or just refresh coordinator based on what changed.

    For runtime options that have corresponding entities (switches, numbers),
    we only need to refresh the coordinator. For structural changes, we need a full reload.
    """
    # These keys can be changed at runtime via their corresponding entities
    # without requiring a full reload. The list is centrally defined in config.py
    # based on the runtime_configurable flag in CONF_SPECS.
    runtime_configurable_keys = get_runtime_configurable_keys()

    if hasattr(entry, "runtime_data") and entry.runtime_data:
        coordinator = entry.runtime_data.coordinator

        # Get the old configuration that the coordinator was using
        old_config = coordinator._merged_config

        # Get the new configuration from the updated entry (all settings are in options)
        new_config = dict(getattr(entry, HA_OPTIONS, {}) or {})

        # Determine which keys have actually changed
        changed_keys = {key for key in set(old_config.keys()) | set(new_config.keys()) if old_config.get(key) != new_config.get(key)}
        changes = ", ".join(f"{key}={new_config.get(key)}" for key in sorted(changed_keys))

        # If the only changes are to runtime-configurable keys, just refresh
        if changed_keys and changed_keys.issubset(runtime_configurable_keys):
            LOGGER.info(f"Runtime settings change detected ({changes}), refreshing coordinator")

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
