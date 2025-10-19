"""Tests for Smart Cover Automation service registration and handling.

This module tests the logbook_entry service that is registered during integration
setup, including service call handling, parameter validation, and coordinator routing.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smart_cover_automation import async_setup_entry
from custom_components.smart_cover_automation.const import (
    DATA_COORDINATORS,
    DOMAIN,
    SERVICE_LOGBOOK_ENTRY,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import MOCK_COVER_ENTITY_ID, MockConfigEntry, create_temperature_config


class TestServiceRegistration:
    """Test suite for service registration during integration setup."""

    async def test_service_registered_on_first_setup(self, mock_hass_with_spec) -> None:
        """Test that logbook_entry service is registered on first integration setup."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        # Mock coordinator and integration loading
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Execute setup
            result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        # Verify service was registered
        assert result is True
        mock_hass_with_spec.services.async_register.assert_called_once()
        call_args = mock_hass_with_spec.services.async_register.call_args
        assert call_args[0][0] == DOMAIN
        assert call_args[0][1] == SERVICE_LOGBOOK_ENTRY

    async def test_service_not_registered_twice(self, mock_hass_with_spec) -> None:
        """Test that service is not re-registered if already exists."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        # Simulate service already registered
        mock_hass_with_spec.services.has_service = MagicMock(return_value=True)

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        assert result is True
        # Verify service registration was skipped
        mock_hass_with_spec.services.async_register.assert_not_called()


class TestServiceHandler:
    """Test suite for logbook_entry service handler."""

    @pytest.fixture
    def mock_service_call(self) -> MagicMock:
        """Create a mock service call."""
        call = MagicMock()
        call.data = {
            "entity_id": MOCK_COVER_ENTITY_ID,
            "target_position": 50,
            "verb_key": "verb_opening",
            "reason_key": "reason_heat_protection",
        }
        return call

    async def test_service_handler_with_valid_data(self, mock_hass_with_spec, mock_service_call) -> None:
        """Test service handler processes valid service call."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator._add_logbook_entry_cover_movement = AsyncMock()
            mock_coordinator.data = {"covers": {MOCK_COVER_ENTITY_ID: {}}}
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            # Get the registered service handler
            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            # Call the service
            await service_handler(mock_service_call)

            # Verify logbook entry was created
            mock_coordinator._add_logbook_entry_cover_movement.assert_called_once_with(
                verb_key="verb_opening",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_heat_protection",
                target_pos=50,
            )

    async def test_service_handler_no_coordinators(self, mock_hass_with_spec, mock_service_call, caplog) -> None:
        """Test service handler when no coordinators are registered."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            caplog.at_level("WARNING", logger="custom_components.smart_cover_automation"),
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            # Clear coordinators
            mock_hass_with_spec.data[DOMAIN][DATA_COORDINATORS] = {}

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            await service_handler(mock_service_call)

            assert "no coordinators are registered" in caplog.text

    async def test_service_handler_missing_entity_id(self, mock_hass_with_spec, caplog) -> None:
        """Test service handler with missing entity_id parameter."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            caplog.at_level("WARNING", logger="custom_components.smart_cover_automation"),
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            # Call without entity_id
            call = MagicMock()
            call.data = {"target_position": 50}

            await service_handler(call)

            assert "requires 'entity_id' and 'target_position'" in caplog.text

    async def test_service_handler_missing_target_position(self, mock_hass_with_spec, caplog) -> None:
        """Test service handler with missing target_position parameter."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            caplog.at_level("WARNING", logger="custom_components.smart_cover_automation"),
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            call = MagicMock()
            call.data = {"entity_id": MOCK_COVER_ENTITY_ID}

            await service_handler(call)

            assert "requires 'entity_id' and 'target_position'" in caplog.text

    async def test_service_handler_invalid_target_position(self, mock_hass_with_spec, caplog) -> None:
        """Test service handler with invalid target_position value."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            caplog.at_level("WARNING", logger="custom_components.smart_cover_automation"),
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            call = MagicMock()
            call.data = {
                "entity_id": MOCK_COVER_ENTITY_ID,
                "target_position": "invalid",
            }

            await service_handler(call)

            assert "Invalid target_position" in caplog.text

    async def test_service_handler_with_config_entry_id(self, mock_hass_with_spec, mock_service_call) -> None:
        """Test service handler routes to specific coordinator by config_entry_id."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator._add_logbook_entry_cover_movement = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            # Add config_entry_id to service call
            mock_service_call.data["config_entry_id"] = mock_config_entry.entry_id

            await service_handler(mock_service_call)

            mock_coordinator._add_logbook_entry_cover_movement.assert_called_once()

    async def test_service_handler_routes_by_cover_entity(self, mock_hass_with_spec, mock_service_call) -> None:
        """Test service handler finds coordinator by cover entity ID."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator._add_logbook_entry_cover_movement = AsyncMock()
            mock_coordinator.data = {"covers": {MOCK_COVER_ENTITY_ID: {}}}
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            await service_handler(mock_service_call)

            mock_coordinator._add_logbook_entry_cover_movement.assert_called_once()

    async def test_service_handler_fallback_to_first_coordinator(self, mock_hass_with_spec) -> None:
        """Test service handler falls back to first available coordinator."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator._add_logbook_entry_cover_movement = AsyncMock()
            mock_coordinator.data = {"covers": {}}  # No matching cover
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            call = MagicMock()
            call.data = {
                "entity_id": "cover.other_cover",
                "target_position": 50,
            }

            await service_handler(call)

            # Should use the only available coordinator
            mock_coordinator._add_logbook_entry_cover_movement.assert_called_once()

    async def test_service_handler_no_coordinator_found(self, mock_hass_with_spec, mock_service_call, caplog) -> None:
        """Test service handler when no coordinator can be located."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            caplog.at_level("WARNING", logger="custom_components.smart_cover_automation"),
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            # Clear all coordinators - test None values don't cause AttributeError
            mock_hass_with_spec.data[DOMAIN][DATA_COORDINATORS] = {"some_id": None}

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            await service_handler(mock_service_call)

            assert "could not locate an active coordinator" in caplog.text

    async def test_service_handler_with_default_verb_and_reason(self, mock_hass_with_spec) -> None:
        """Test service handler uses default verb and reason keys when not provided."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator._add_logbook_entry_cover_movement = AsyncMock()
            mock_coordinator.data = {"covers": {}}
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

            service_handler = mock_hass_with_spec.services.async_register.call_args[0][2]

            call = MagicMock()
            call.data = {
                "entity_id": MOCK_COVER_ENTITY_ID,
                "target_position": 75,
                # No verb_key or reason_key provided
            }

            await service_handler(call)

            # Verify defaults were used
            call_kwargs = mock_coordinator._add_logbook_entry_cover_movement.call_args.kwargs
            assert call_kwargs["verb_key"] == "verb_opening"
            assert call_kwargs["reason_key"] == "reason_heat_protection"
