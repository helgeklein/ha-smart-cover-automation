"""Tests for Smart Cover Automation entity base classes.

This module tests the foundational entity classes that provide common functionality
for all Smart Cover Automation entities in Home Assistant. The tests validate:

- Entity initialization and configuration
- Device information setup and registration
- Unique identifier generation and consistency
- Coordinator integration and data access
- Home Assistant entity framework compliance

The IntegrationEntity base class serves as the foundation for all platform-specific
entities (sensors, binary sensors, switches) and ensures consistent behavior across
the integration. These tests verify that entities are properly initialized with
correct device associations and unique identifiers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.smart_cover_automation.const import DOMAIN
from custom_components.smart_cover_automation.entity import IntegrationEntity


class TestIntegrationEntity:
    """Test suite for the IntegrationEntity base class.

    This test class validates the core functionality of the IntegrationEntity
    base class, which provides common behavior for all Smart Cover Automation
    entities in Home Assistant. The tests ensure:

    - Proper entity initialization with coordinator integration
    - Correct device information setup for Home Assistant device registry
    - Unique identifier generation that matches configuration entry IDs
    - Coordinator reference maintenance for data access
    - Compliance with Home Assistant entity framework requirements

    The IntegrationEntity class is the foundation for all platform-specific
    entities (sensors, binary sensors, switches) in the integration.
    """

    def test_entity_initialization(self, mock_config_entry_basic) -> None:
        """Test proper initialization of IntegrationEntity with coordinator.

        Validates that the IntegrationEntity base class correctly initializes
        when provided with a coordinator instance. This test ensures:

        - Base class does not set unique ID (subclasses handle their own IDs)
        - Device information is correctly populated for Home Assistant device registry
        - Device identifiers are properly formatted with domain and entry ID
        - All required entity properties are set during initialization

        The device information is critical for Home Assistant to properly
        group entities under a single device in the device registry.
        """
        # Create mock coordinator with configuration entry
        coordinator = MagicMock()
        coordinator.config_entry = mock_config_entry_basic

        # Initialize the entity with the coordinator
        entity = IntegrationEntity(coordinator)

        # Verify unique ID is None for base class (subclasses set their own unique IDs)
        assert entity.unique_id is None, f"Base IntegrationEntity should not set unique_id, got {entity.unique_id}"

        # Verify device information is properly populated
        device_info = entity.device_info
        assert device_info, "Device info should be set"

        # Verify device identifier includes domain and entry ID
        identifiers = device_info.get("identifiers", set())
        expected_identifier = (DOMAIN, mock_config_entry_basic.entry_id)
        assert expected_identifier in identifiers, f"Expected identifier {expected_identifier} not found in {identifiers}"

    def test_coordinator_reference(self, mock_config_entry_basic) -> None:
        """Test that entity maintains proper reference to its coordinator.

        Validates that the IntegrationEntity correctly stores and maintains
        a reference to the DataUpdateCoordinator that was passed during
        initialization. This coordinator reference is essential for:

        - Accessing current automation data and sensor readings
        - Receiving updates when automation state changes
        - Maintaining synchronization with the automation logic
        - Providing entity state based on coordinator data

        The coordinator serves as the primary data source for all entities
        in the Smart Cover Automation integration.
        """
        # Create mock coordinator with configuration entry
        coordinator = MagicMock()
        coordinator.config_entry = mock_config_entry_basic

        # Initialize the entity with the coordinator
        entity = IntegrationEntity(coordinator)

        # Verify entity maintains reference to the coordinator
        assert entity.coordinator == coordinator, "Entity should maintain reference to coordinator"
