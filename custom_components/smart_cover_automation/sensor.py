"""Sensor platform for smart_cover_automation.

Reports values from the DataUpdateCoordinator. Availability and native_value
are provided via cached properties to align with modern HA entity patterns.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="smart_cover_automation",
        name="Integration Sensor",
        icon="mdi:format-quote-close",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        IntegrationSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationSensor(IntegrationEntity, SensorEntity):
    """smart_cover_automation Sensor class."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description

    @cached_property
    def available(self) -> bool | None:  # type: ignore[override]
        """Return availability; unify base class types for type checkers."""
        return super().available

    @cached_property
    def native_value(self) -> str | None:  # type: ignore[override]
        """Return the native value of the sensor."""
        return self.coordinator.data.get("body")
