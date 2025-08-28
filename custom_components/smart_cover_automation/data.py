"""Custom types for smart_cover_automation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration
    from .coordinator import DataUpdateCoordinator


type IntegrationConfigEntry = ConfigEntry[IntegrationData]


@dataclass
class IntegrationData:
    """Data for the integration."""

    coordinator: DataUpdateCoordinator
    integration: Integration
    config: dict[str, Any]  # Configuration data from the config entry
