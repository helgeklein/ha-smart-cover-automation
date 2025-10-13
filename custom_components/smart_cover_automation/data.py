"""Runtime data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .coordinator import DataUpdateCoordinator


# Type safety: entry.runtime_data will be of type RuntimeData
type IntegrationConfigEntry = ConfigEntry[RuntimeData]


class _CoordinatorDataRequired(TypedDict):
    """Required fields in coordinator data."""

    covers: dict[str, Any]  # Dictionary mapping cover entity IDs to their per-cover attributes


class CoordinatorData(_CoordinatorDataRequired, total=False):
    """Type-safe structure for coordinator data.

    This TypedDict ensures type safety for all values stored in the coordinator's data
    dictionary. It defines the expected types for sensor attributes that are exposed
    to Home Assistant entities.

    The 'covers' key is always required (even if empty), while other keys are optional
    and may not be present depending on automation state.

    Attributes:
        covers: Dictionary mapping cover entity IDs to their per-cover attributes (always present)
        sun_azimuth: Current sun azimuth angle in degrees (0° to 360°)
        sun_elevation: Current sun elevation angle in degrees (-90° to +90°)
        temp_current_max: Current maximum temperature forecast in degrees Celsius
        temp_hot: Whether the temperature is above threshold (hot day indicator)
        weather_sunny: Whether the weather condition is sunny or partly cloudy
        message: Optional automation status message
    """

    # Optional keys - may not be present depending on automation state
    sun_azimuth: float
    sun_elevation: float
    temp_current_max: float
    temp_hot: bool
    weather_sunny: bool
    message: str


@dataclass
class RuntimeData:
    """Data for the integration."""

    coordinator: DataUpdateCoordinator
    integration: Integration
    config: dict[str, Any]
