"""Implementation of the automation logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator as BaseCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import const
from .automation_engine import AutomationEngine
from .config import ConfKeys, ResolvedConfig, resolve_entry
from .data import CoordinatorData
from .ha_interface import HomeAssistantInterface, WeatherEntityNotFoundError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

    from .data import IntegrationConfigEntry


#
# Exception classes
#
class SmartCoverError(UpdateFailed):
    """Base class for this integration's errors."""


class SunSensorNotFoundError(SmartCoverError):
    """Sun sensor could not be found."""

    def __init__(self, sensor_name: str) -> None:
        super().__init__(f"Sun sensor '{sensor_name}' not found")
        self.sensor_name = sensor_name


#
# DataUpdateCoordinator
#
class DataUpdateCoordinator(BaseCoordinator[CoordinatorData]):
    """Automation engine."""

    config_entry: IntegrationConfigEntry

    #
    # __init__
    #
    def __init__(self, hass: HomeAssistant, config_entry: IntegrationConfigEntry) -> None:
        super().__init__(
            hass,
            const.LOGGER,
            name=const.DOMAIN,
            update_interval=const.UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self.config_entry = config_entry

        # Store merged config for comparison during reload
        self._merged_config: dict[str, Any] = {}

        resolved = resolve_entry(config_entry)
        const.LOGGER.info(f"Initializing coordinator: update_interval={const.UPDATE_INTERVAL.total_seconds()} s")

        # Create the HA interface layer
        self._ha_interface = HomeAssistantInterface(hass, self._resolved_settings)

        # Initialize the automation engine (persists across runs)
        self._automation_engine = AutomationEngine(
            resolved=resolved,
            config=config_entry.runtime_data.config,
            ha_interface=self._ha_interface,
        )

        # Adjust log level if verbose logging is enabled
        try:
            if resolved.verbose_logging:
                const.LOGGER.setLevel(logging.DEBUG)
                const.LOGGER.debug("Verbose logging enabled")
        except Exception:
            pass

    #
    # status_sensor_unique_id
    #
    @property
    def status_sensor_unique_id(self) -> str | None:
        """Get the unique_id of the status binary sensor."""

        return self._ha_interface.status_sensor_unique_id

    #
    # status_sensor_unique_id setter
    #
    @status_sensor_unique_id.setter
    def status_sensor_unique_id(self, value: str | None) -> None:
        """Set the unique_id of the status binary sensor."""

        self._ha_interface.status_sensor_unique_id = value

    #
    # _resolved_settings
    #
    def _resolved_settings(self) -> ResolvedConfig:
        """Return resolved settings from the config entry options."""

        from .config import resolve

        # Get configuration from options (all user settings are stored there)
        opts = dict(getattr(self.config_entry, const.HA_OPTIONS, {}) or {})

        return resolve(opts)

    #
    # _async_update_data
    #
    async def _async_update_data(self) -> CoordinatorData:
        """Update automation state and control covers.

        This is the heart of the automation logic. It evaluates sensor states and
        controls covers as needed.

        This is called by HA in the following cases:
        - First refresh
        - Periodically at update_interval
        - Manual refresh
        - Integration reload

        Returns:
        CoordinatorData that stores details of the last automation run.
        Data entries are converted to HA entity attributes which are visible
        in the integration's automation sensor.

        Raises:
        UpdateFailed: For critical errors that should make entities unavailable
        """

        # Prepare minimal valid state to keep integration entities available
        error_result: CoordinatorData = {ConfKeys.COVERS.value: {}}

        try:
            const.LOGGER.info("Starting cover automation update")

            # Keep a reference to raw config for dynamic per-cover direction
            config = self.config_entry.runtime_data.config

            # Get the resolved settings - configuration errors are critical
            try:
                resolved = self._resolved_settings()
            except Exception as err:
                # Configuration resolution failure is critical - entities should be unavailable
                const.LOGGER.error(f"Critical configuration error: {err}")
                raise UpdateFailed(f"Configuration error: {err}") from err

            # Collect states for all configured covers
            covers = tuple(resolved.covers)
            states: dict[str, State | None] = {entity_id: self.hass.states.get(entity_id) for entity_id in covers}

            # Update the resolved config and raw config in the persistent engine
            # (These may change when user updates options)
            self._automation_engine.resolved = resolved
            self._automation_engine.config = config

            # Run the automation logic
            return await self._automation_engine.run(states)

        except (SunSensorNotFoundError, WeatherEntityNotFoundError) as err:
            # Critical sensor errors - these make the automation non-functional
            const.LOGGER.error(f"Critical sensor error: {err}")
            raise UpdateFailed(str(err)) from err
        except UpdateFailed:
            # Re-raise other UpdateFailed exceptions (critical errors)
            raise
        except Exception as err:
            # Unexpected errors - log but continue operation to maintain system stability
            const.LOGGER.error(f"Unexpected error during automation update: {err}")
            const.LOGGER.debug(f"Exception details: {type(err).__name__}: {err}", exc_info=True)

            # For unexpected errors, return empty result to keep entities available
            # This prevents system instability from unknown issues
            return error_result
