"""Runtime data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .coordinator import DataUpdateCoordinator


# Type safety: entry.runtime_data will be of type RuntimeData
type IntegrationConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Data for the integration."""

    coordinator: DataUpdateCoordinator
    integration: Integration
    config: dict[str, Any]
