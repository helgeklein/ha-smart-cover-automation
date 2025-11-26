"""Runtime data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .const import LockMode
    from .coordinator import DataUpdateCoordinator


# Type safety: entry.runtime_data will be of type RuntimeData
type IntegrationConfigEntry = ConfigEntry[RuntimeData]


#
# CoordinatorData
#
@dataclass
class CoordinatorData:
    """Type-safe structure for coordinator data.

    This dataclass ensures type safety for all values stored in the coordinator's data.
    It defines the expected types for sensor attributes that are exposed to Home Assistant
    entities.

    The 'covers' field is always required (even if empty dict), while other fields are
    optional and may be None depending on automation state.

    Attributes:
        covers: Dictionary mapping cover entity IDs to their per-cover attributes (required)
        sun_azimuth: Current sun azimuth angle in degrees (0° to 360°)
        sun_elevation: Current sun elevation angle in degrees (-90° to +90°)
        temp_current_max: Current maximum temperature forecast in degrees Celsius
        temp_hot: Whether the temperature is above threshold (hot day indicator)
        weather_sunny: Whether the weather condition is sunny or partly cloudy
        lock_mode: Current lock mode setting
        lock_active: Whether any lock mode is active (not unlocked)
    """

    # Required field
    covers: dict[str, Any]

    # Optional fields - may be None depending on automation state
    sun_azimuth: float | None = None
    sun_elevation: float | None = None
    temp_current_max: float | None = None
    temp_hot: bool | None = None
    weather_sunny: bool | None = None
    lock_mode: LockMode | None = None
    lock_active: bool | None = None


@dataclass
class RuntimeData:
    """Data for the integration."""

    coordinator: DataUpdateCoordinator
    integration: Integration
    config: dict[str, Any]
