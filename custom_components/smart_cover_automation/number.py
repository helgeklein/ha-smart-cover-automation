"""Number platform for smart_cover_automation.

This module provides number entities that allow users to configure various
numeric settings of the Smart Cover Automation integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import (  # pyright: ignore[reportMissingImports]
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime  # pyright: ignore[reportMissingImports]

from .config import ConfKeys
from .const import (
    COVER_SFX_TILT_EXTERNAL_VALUE_DAY,
    COVER_SFX_TILT_EXTERNAL_VALUE_NIGHT,
    COVER_SFX_TILT_MODE_DAY,
    COVER_SFX_TILT_MODE_NIGHT,
    NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_DAY,
    NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_NIGHT,
    NUMBER_KEY_DAILY_MAX_TEMPERATURE_THRESHOLD,
    NUMBER_KEY_DAILY_MIN_TEMPERATURE_THRESHOLD,
    NUMBER_KEY_MANUAL_OVERRIDE_DURATION,
    NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
    NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
    NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY,
    NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT,
    TiltMode,
)
from .entity import IntegrationEntity
from .util import cover_supports_tilt, to_int_or_none

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant  # pyright: ignore[reportMissingImports]
    from homeassistant.helpers.entity_platform import AddEntitiesCallback  # pyright: ignore[reportMissingImports]

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


#
# async_setup_entry
#
async def async_setup_entry(
    hass: HomeAssistant,
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
    resolved = coordinator._resolved_settings()

    # Create all number entities
    entities = [
        ManualOverrideDurationNumber(coordinator),
        SunAzimuthToleranceNumber(coordinator),
        SunElevationThresholdNumber(coordinator),
        DailyMaxTemperatureThresholdNumber(coordinator),
        DailyMinTemperatureThresholdNumber(coordinator),
    ]

    if resolved.tilt_mode_day == TiltMode.EXTERNAL:
        entities.append(GlobalExternalTiltDayNumber(coordinator))

    if resolved.tilt_mode_night == TiltMode.EXTERNAL:
        entities.append(GlobalExternalTiltNightNumber(coordinator))

    options = dict(coordinator.config_entry.options or {})
    for cover_entity_id in resolved.covers:
        supports_tilt = cover_supports_tilt(hass, cover_entity_id)
        if supports_tilt is False:
            continue

        if options.get(f"{cover_entity_id}_{COVER_SFX_TILT_MODE_DAY}") == TiltMode.EXTERNAL:
            entities.append(CoverExternalTiltDayNumber(coordinator, cover_entity_id))
        if options.get(f"{cover_entity_id}_{COVER_SFX_TILT_MODE_NIGHT}") == TiltMode.EXTERNAL:
            entities.append(CoverExternalTiltNightNumber(coordinator, cover_entity_id))

    async_add_entities(entities)


#
# _format_cover_name
#
def _format_cover_name(coordinator: DataUpdateCoordinator, cover_entity_id: str) -> str:
    """Return a human-friendly name for a cover entity."""

    state = coordinator.hass.states.get(cover_entity_id)
    if state is not None:
        friendly_name = state.attributes.get("friendly_name")
        if isinstance(friendly_name, str) and friendly_name.strip():
            return friendly_name.strip()

    object_id = cover_entity_id.split(".", 1)[-1]
    return object_id.replace("_", " ").strip().title()


#
# IntegrationNumber
#
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

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: NumberEntityDescription,
        config_key: str,
    ) -> None:
        """Initialize the number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number entity
            entity_description: Configuration describing the entity's properties
                               (name, icon, min/max values, etc.)
            config_key: The configuration key this number entity controls
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this number's characteristics
        self.entity_description = entity_description

        # Store the config key this number entity controls
        self._config_key = config_key

        # Set unique ID to ensure proper device grouping and entity identification
        # This will result in entity_id: number.smart_cover_automation_{translation_key}
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"

    # Note: We inherit the 'available' property from IntegrationEntity/CoordinatorEntity
    # which provides the correct coordinator-based availability logic.
    # No override is needed since the default behavior is exactly what we want.

    #
    # native_value
    #
    @property
    def native_value(self) -> float:  # pyright: ignore
        """Return the current value of the number entity.

        Reads from the resolved settings to get the current state.
        This reflects changes made through the integration's options flow.
        """
        resolved = self.coordinator._resolved_settings()
        return float(getattr(resolved, self._config_key.lower()))

    #
    # async_set_native_value
    #
    async def async_set_native_value(self, value: float) -> None:
        """Update the number entity value.

        Sets the config value and triggers a coordinator refresh
        to immediately apply the new setting.

        Args:
            value: The new value for the number entity
        """
        await self._async_persist_option(self._config_key, value)

    #
    # _async_persist_option
    #
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


#
# ExternalTiltNumber
#
class ExternalTiltNumber(IntegrationNumber):
    """Base number entity for externally supplied tilt angle values."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: NumberEntityDescription,
        config_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize an external tilt number entity."""

        super().__init__(coordinator, entity_description, config_key)
        if translation_placeholders is not None:
            self._attr_translation_placeholders = translation_placeholders

    @property
    def native_value(self) -> float | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return the currently stored external tilt value, if any."""

        options = dict(self.coordinator.config_entry.options or {})
        value = to_int_or_none(options.get(self._config_key))
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Persist a new external tilt value."""

        await self._async_persist_option(self._config_key, int(value))


#
# ManualOverrideDurationNumber
#
class ManualOverrideDurationNumber(IntegrationNumber):
    """Number entity for manual override duration in minutes.

    Allows users to configure how long the automation should be paused
    after a cover has been moved manually. Value is stored internally
    in seconds but displayed/edited in minutes for better UX.
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the manual override duration number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number entity
        """
        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_MANUAL_OVERRIDE_DURATION,
            translation_key=NUMBER_KEY_MANUAL_OVERRIDE_DURATION,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:timer-outline",
            native_min_value=0,
            native_max_value=None,  # Unlimited
            native_step=1,
            mode=NumberMode.BOX,
            native_unit_of_measurement=UnitOfTime.MINUTES,
        )
        super().__init__(coordinator, entity_description, ConfKeys.MANUAL_OVERRIDE_DURATION.value)

    @property
    def native_value(self) -> float:
        """Return the current value in minutes.

        The internal storage is in seconds, so we convert to minutes
        for display in the UI.
        """
        resolved = self.coordinator._resolved_settings()
        seconds = resolved.manual_override_duration
        return float(seconds) / 60.0

    async def async_set_native_value(self, value: float) -> None:
        """Update the value, converting from minutes to seconds.

        Args:
            value: Duration in minutes from the UI
        """
        seconds = int(value * 60)
        await self._async_persist_option(ConfKeys.MANUAL_OVERRIDE_DURATION.value, seconds)


#
# DailyMaxTemperatureThresholdNumber
#
class DailyMaxTemperatureThresholdNumber(IntegrationNumber):
    """Number entity for controlling the daily max temperature threshold for heat protection."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the daily max temperature threshold number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                         and provides state management for this number entity
        """
        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_DAILY_MAX_TEMPERATURE_THRESHOLD,
            translation_key=NUMBER_KEY_DAILY_MAX_TEMPERATURE_THRESHOLD,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer-high",
            native_min_value=-100,
            native_max_value=100,
            native_step=0.5,
            mode=NumberMode.BOX,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        super().__init__(coordinator, entity_description, ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value)


#
# DailyMinTemperatureThresholdNumber
#
class DailyMinTemperatureThresholdNumber(IntegrationNumber):
    """Number entity for controlling the daily min temperature threshold for heat protection."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the daily min temperature threshold number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                         and provides state management for this number entity
        """
        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_DAILY_MIN_TEMPERATURE_THRESHOLD,
            translation_key=NUMBER_KEY_DAILY_MIN_TEMPERATURE_THRESHOLD,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer-low",
            native_min_value=-100,
            native_max_value=100,
            native_step=0.5,
            mode=NumberMode.BOX,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        super().__init__(coordinator, entity_description, ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value)


#
# GlobalExternalTiltDayNumber
#
class GlobalExternalTiltDayNumber(ExternalTiltNumber):
    """Global external tilt value used during daytime."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the global daytime external tilt number."""

        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY,
            translation_key=NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:blinds-horizontal",
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            mode=NumberMode.BOX,
            native_unit_of_measurement="%",
        )
        super().__init__(coordinator, entity_description, NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY)


#
# GlobalExternalTiltNightNumber
#
class GlobalExternalTiltNightNumber(ExternalTiltNumber):
    """Global external tilt value used during night/evening closure."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the global nighttime external tilt number."""

        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT,
            translation_key=NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:blinds-horizontal",
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            mode=NumberMode.BOX,
            native_unit_of_measurement="%",
        )
        super().__init__(coordinator, entity_description, NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT)


#
# CoverExternalTiltDayNumber
#
class CoverExternalTiltDayNumber(ExternalTiltNumber):
    """Per-cover external tilt value used during daytime."""

    def __init__(self, coordinator: DataUpdateCoordinator, cover_entity_id: str) -> None:
        """Initialize the per-cover daytime external tilt number."""

        cover_name = _format_cover_name(coordinator, cover_entity_id)
        config_key = f"{cover_entity_id}_{COVER_SFX_TILT_EXTERNAL_VALUE_DAY}"
        entity_description = NumberEntityDescription(
            key=config_key,
            translation_key=NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_DAY,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:blinds-horizontal",
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            mode=NumberMode.BOX,
            native_unit_of_measurement="%",
        )
        super().__init__(coordinator, entity_description, config_key, {"cover_name": cover_name})


#
# CoverExternalTiltNightNumber
#
class CoverExternalTiltNightNumber(ExternalTiltNumber):
    """Per-cover external tilt value used during night/evening closure."""

    def __init__(self, coordinator: DataUpdateCoordinator, cover_entity_id: str) -> None:
        """Initialize the per-cover nighttime external tilt number."""

        cover_name = _format_cover_name(coordinator, cover_entity_id)
        config_key = f"{cover_entity_id}_{COVER_SFX_TILT_EXTERNAL_VALUE_NIGHT}"
        entity_description = NumberEntityDescription(
            key=config_key,
            translation_key=NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_NIGHT,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:blinds-horizontal",
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            mode=NumberMode.BOX,
            native_unit_of_measurement="%",
        )
        super().__init__(coordinator, entity_description, config_key, {"cover_name": cover_name})


#
# SunAzimuthToleranceNumber
#
class SunAzimuthToleranceNumber(IntegrationNumber):
    """Number entity for controlling the sun azimuth tolerance."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sun azimuth tolerance number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number entity
        """
        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
            translation_key=NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:sun-compass",
            native_min_value=0,
            native_max_value=180,
            native_step=1,
            mode=NumberMode.BOX,
            native_unit_of_measurement="°",
        )
        super().__init__(coordinator, entity_description, ConfKeys.SUN_AZIMUTH_TOLERANCE.value)


#
# SunElevationThresholdNumber
#
class SunElevationThresholdNumber(IntegrationNumber):
    """Number entity for controlling the sun elevation threshold."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sun elevation threshold number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number entity
        """
        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
            translation_key=NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
            entity_category=EntityCategory.CONFIG,
            icon="mdi:sun-angle-outline",
            native_min_value=0,
            native_max_value=90,
            native_step=1,
            mode=NumberMode.BOX,
            native_unit_of_measurement="°",
        )
        super().__init__(coordinator, entity_description, ConfKeys.SUN_ELEVATION_THRESHOLD.value)
