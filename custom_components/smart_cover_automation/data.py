"""Custom types for smart_cover_automation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol


class _TitleClient(Protocol):
    async def async_set_title(self, title: str) -> None: ...


if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .coordinator import DataUpdateCoordinator
    from .settings import Settings


type IntegrationConfigEntry = ConfigEntry[IntegrationData]


@dataclass
class IntegrationData:
    """Data for the integration."""

    coordinator: DataUpdateCoordinator
    integration: Integration
    config: dict[str, Any]  # Configuration data from the config entry
    client: _TitleClient | None = None
    # Typed settings built from entry.options (overrides) and entry.data
    settings: Settings | None = None
