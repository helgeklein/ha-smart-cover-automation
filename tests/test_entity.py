"""Tests for entity classes."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.smart_cover_automation.const import DOMAIN
from custom_components.smart_cover_automation.entity import IntegrationEntity

from .conftest import MockConfigEntry, create_temperature_config


class TestIntegrationEntity:
    """Test IntegrationEntity base class."""

    def test_entity_initialization(self) -> None:
        """Test entity initialization."""
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = MagicMock()
        coordinator.config_entry = config_entry

        entity = IntegrationEntity(coordinator)

        # Verify entity properties
        expected_uid = config_entry.entry_id
        assert entity.unique_id == expected_uid, f"Expected unique_id {expected_uid}, got {entity.unique_id}"

        device_info = entity.device_info
        assert device_info, "Device info should be set"

        identifiers = device_info.get("identifiers", set())
        expected_identifier = (DOMAIN, config_entry.entry_id)
        assert expected_identifier in identifiers, f"Expected identifier {expected_identifier} not found in {identifiers}"

    def test_coordinator_reference(self) -> None:
        """Test that entity maintains reference to coordinator."""
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = MagicMock()
        coordinator.config_entry = config_entry

        entity = IntegrationEntity(coordinator)

        assert entity.coordinator == coordinator, "Entity should maintain reference to coordinator"
