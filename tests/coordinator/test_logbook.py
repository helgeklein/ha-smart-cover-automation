"""Tests for logbook entry creation.

This module tests the _add_logbook_entry_cover_movement method in the
DataUpdateCoordinator, including translation handling, entity registry lookups,
and error handling.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers import entity_registry as ha_entity_registry

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import MOCK_COVER_ENTITY_ID, MockConfigEntry, create_sun_config


class TestLogbookEntries:
    """Test suite for logbook entry creation."""

    @pytest.fixture
    def mock_coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a coordinator for testing."""
        # Setup config.language for translation calls
        mock_hass.config = MagicMock()
        mock_hass.config.language = "en"

        config_data = create_sun_config()
        config_entry = MockConfigEntry(config_data)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        return coordinator

    @pytest.fixture
    def mock_registry(self) -> MagicMock:
        """Create a mock entity registry."""
        registry = MagicMock()
        # entities is a dict-like object that supports .values()
        registry.entities = {}
        return registry

    @pytest.fixture
    def mock_translations(self) -> dict[str, str]:
        """Create mock translations."""
        base_key = f"component.{const.DOMAIN}.services.{const.TRANSL_LOGBOOK}"
        return {
            f"{base_key}.verb_opening": "Opening",
            f"{base_key}.verb_closing": "Closing",
            f"{base_key}.reason_heat_protection": "protect from heat",
            f"{base_key}.reason_let_light_in": "let light in",
            f"{base_key}.{const.TRANSL_LOGBOOK_TEMPLATE_COVER_MOVEMENT}": "{verb} {entity_id} to {reason}. New position: {position}%.",
        }

    async def test_logbook_entry_with_valid_entity(
        self,
        mock_coordinator: DataUpdateCoordinator,
        mock_registry: MagicMock,
        mock_translations: dict[str, str],
    ) -> None:
        """Test creating a logbook entry with a valid entity."""
        # Setup
        unique_id = "test_unique_id"
        integration_entity_id = f"binary_sensor.{const.DOMAIN}_status"
        mock_coordinator.status_sensor_unique_id = unique_id

        # Create mock registry entry - registry.entities is a dict-like object
        mock_entity = MagicMock()
        mock_entity.unique_id = unique_id
        mock_entity.platform = const.DOMAIN
        mock_entity.entity_id = integration_entity_id
        mock_registry.entities = {"test_entity_registry_id": mock_entity}

        with (
            patch.object(ha_entity_registry, "async_get", return_value=mock_registry),
            patch(
                "custom_components.smart_cover_automation.coordinator.translation.async_get_translations", new_callable=AsyncMock
            ) as mock_get_translations,
            patch("custom_components.smart_cover_automation.coordinator.async_log_entry") as mock_log_entry,
        ):
            mock_get_translations.return_value = mock_translations

            # Execute
            await mock_coordinator._add_logbook_entry_cover_movement(
                verb_key="verb_opening",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_heat_protection",
                target_pos=50,
            )

            # Verify
            mock_log_entry.assert_called_once()
            call_kwargs = mock_log_entry.call_args.kwargs
            assert call_kwargs["name"] == const.INTEGRATION_NAME
            assert call_kwargs["domain"] == const.DOMAIN
            assert call_kwargs["entity_id"] == integration_entity_id
            assert "Opening" in call_kwargs["message"]
            assert MOCK_COVER_ENTITY_ID in call_kwargs["message"]
            assert "protect from heat" in call_kwargs["message"]
            assert "50%" in call_kwargs["message"]

    async def test_logbook_entry_entity_not_found(
        self,
        mock_coordinator: DataUpdateCoordinator,
        mock_registry: MagicMock,
        mock_translations: dict[str, str],
    ) -> None:
        """Test that logbook entry handles missing entity gracefully."""
        # Setup - no matching entity in registry
        unique_id = "test_unique_id"
        mock_coordinator.status_sensor_unique_id = unique_id
        mock_registry.entities = {}

        with (
            patch.object(ha_entity_registry, "async_get", return_value=mock_registry),
            patch(
                "custom_components.smart_cover_automation.coordinator.translation.async_get_translations", new_callable=AsyncMock
            ) as mock_get_translations,
            patch("custom_components.smart_cover_automation.coordinator.async_log_entry") as mock_log_entry,
            patch.object(const.LOGGER, "warning") as mock_warning,
        ):
            mock_get_translations.return_value = mock_translations

            # Execute
            await mock_coordinator._add_logbook_entry_cover_movement(
                verb_key="verb_opening",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_heat_protection",
                target_pos=50,
            )

            # Verify - warning logged, no logbook entry created
            mock_warning.assert_called_once()
            assert "Could not find integration entity" in mock_warning.call_args[0][0]
            mock_log_entry.assert_not_called()

    async def test_logbook_entry_missing_translations(
        self,
        mock_coordinator: DataUpdateCoordinator,
        mock_registry: MagicMock,
    ) -> None:
        """Test that logbook entry handles missing translations gracefully."""
        # Setup
        unique_id = "test_unique_id"
        integration_entity_id = f"binary_sensor.{const.DOMAIN}_status"
        mock_coordinator.status_sensor_unique_id = unique_id

        # Create mock registry entry - registry.entities is a dict-like object
        mock_entity = MagicMock()
        mock_entity.unique_id = unique_id
        mock_entity.platform = const.DOMAIN
        mock_entity.entity_id = integration_entity_id
        mock_registry.entities = {"test_entity_registry_id": mock_entity}

        # Empty translations
        empty_translations: dict[str, str] = {}

        with (
            patch.object(ha_entity_registry, "async_get", return_value=mock_registry),
            patch(
                "custom_components.smart_cover_automation.coordinator.translation.async_get_translations", new_callable=AsyncMock
            ) as mock_get_translations,
            patch("custom_components.smart_cover_automation.coordinator.async_log_entry") as mock_log_entry,
            patch.object(const.LOGGER, "warning") as mock_warning,
        ):
            mock_get_translations.return_value = empty_translations

            # Execute
            await mock_coordinator._add_logbook_entry_cover_movement(
                verb_key="verb_opening",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_heat_protection",
                target_pos=50,
            )

            # Verify - warning logged, no logbook entry created
            mock_warning.assert_called_once()
            assert "Missing translations for logbook entry" in mock_warning.call_args[0][0]
            mock_log_entry.assert_not_called()

    async def test_logbook_entry_with_different_verbs(
        self,
        mock_coordinator: DataUpdateCoordinator,
        mock_registry: MagicMock,
        mock_translations: dict[str, str],
    ) -> None:
        """Test logbook entries with different verb keys."""
        # Setup
        unique_id = "test_unique_id"
        integration_entity_id = f"binary_sensor.{const.DOMAIN}_status"
        mock_coordinator.status_sensor_unique_id = unique_id

        mock_entity = MagicMock()
        mock_entity.unique_id = unique_id
        mock_entity.platform = const.DOMAIN
        mock_entity.entity_id = integration_entity_id
        mock_registry.entities = {"test_entity_registry_id": mock_entity}

        with (
            patch.object(ha_entity_registry, "async_get", return_value=mock_registry),
            patch(
                "custom_components.smart_cover_automation.coordinator.translation.async_get_translations", new_callable=AsyncMock
            ) as mock_get_translations,
            patch("custom_components.smart_cover_automation.coordinator.async_log_entry") as mock_log_entry,
        ):
            mock_get_translations.return_value = mock_translations

            # Test opening
            await mock_coordinator._add_logbook_entry_cover_movement(
                verb_key="verb_opening",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_let_light_in",
                target_pos=100,
            )

            assert mock_log_entry.call_count == 1
            message = mock_log_entry.call_args.kwargs["message"]
            assert "Opening" in message
            assert "let light in" in message
            assert "100%" in message

            mock_log_entry.reset_mock()

            # Test closing
            await mock_coordinator._add_logbook_entry_cover_movement(
                verb_key="verb_closing",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_heat_protection",
                target_pos=0,
            )

            assert mock_log_entry.call_count == 1
            message = mock_log_entry.call_args.kwargs["message"]
            assert "Closing" in message
            assert "protect from heat" in message
            assert "0%" in message

    async def test_logbook_entry_exception_handling(
        self,
        mock_coordinator: DataUpdateCoordinator,
        mock_registry: MagicMock,
    ) -> None:
        """Test that exceptions in logbook entry creation are caught and logged."""
        # Setup
        unique_id = "test_unique_id"
        mock_coordinator.status_sensor_unique_id = unique_id

        with (
            patch.object(ha_entity_registry, "async_get", side_effect=Exception("Registry error")),
            patch.object(const.LOGGER, "debug") as mock_debug,
        ):
            # Execute - should not raise exception
            await mock_coordinator._add_logbook_entry_cover_movement(
                verb_key="verb_opening",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_heat_protection",
                target_pos=50,
            )

            # Verify error was logged
            mock_debug.assert_called_once()
            assert "Failed to add logbook entry" in mock_debug.call_args[0][0]

    async def test_logbook_entry_with_various_positions(
        self,
        mock_coordinator: DataUpdateCoordinator,
        mock_registry: MagicMock,
        mock_translations: dict[str, str],
    ) -> None:
        """Test logbook entries with various position values."""
        # Setup
        unique_id = "test_unique_id"
        integration_entity_id = f"binary_sensor.{const.DOMAIN}_status"
        mock_coordinator.status_sensor_unique_id = unique_id

        mock_entity = MagicMock()
        mock_entity.unique_id = unique_id
        mock_entity.platform = const.DOMAIN
        mock_entity.entity_id = integration_entity_id
        mock_registry.entities = {"test_entity_registry_id": mock_entity}

        positions = [0, 25, 50, 75, 100]

        with (
            patch.object(ha_entity_registry, "async_get", return_value=mock_registry),
            patch(
                "custom_components.smart_cover_automation.coordinator.translation.async_get_translations", new_callable=AsyncMock
            ) as mock_get_translations,
            patch("custom_components.smart_cover_automation.coordinator.async_log_entry") as mock_log_entry,
        ):
            mock_get_translations.return_value = mock_translations

            for position in positions:
                mock_log_entry.reset_mock()

                await mock_coordinator._add_logbook_entry_cover_movement(
                    verb_key="verb_opening",
                    entity_id=MOCK_COVER_ENTITY_ID,
                    reason_key="reason_let_light_in",
                    target_pos=position,
                )

                assert mock_log_entry.call_count == 1
                message = mock_log_entry.call_args.kwargs["message"]
                assert f"{position}%" in message

    async def test_logbook_entry_language_fallback(
        self,
        mock_coordinator: DataUpdateCoordinator,
        mock_registry: MagicMock,
    ) -> None:
        """Test that Home Assistant's language fallback mechanism works."""
        # Setup - simulate German language with partial translations
        unique_id = "test_unique_id"
        integration_entity_id = f"binary_sensor.{const.DOMAIN}_status"
        mock_coordinator.status_sensor_unique_id = unique_id

        mock_entity = MagicMock()
        mock_entity.unique_id = unique_id
        mock_entity.platform = const.DOMAIN
        mock_entity.entity_id = integration_entity_id
        mock_registry.entities = {"test_entity_registry_id": mock_entity}

        # Provide German translations
        base_key = f"component.{const.DOMAIN}.services.{const.TRANSL_LOGBOOK}"
        german_translations = {
            f"{base_key}.verb_opening": "Öffne",
            f"{base_key}.verb_closing": "Schließe",
            f"{base_key}.reason_heat_protection": "vor Hitze zu schützen",
            f"{base_key}.reason_let_light_in": "Licht hereinzulassen",
            f"{base_key}.{const.TRANSL_LOGBOOK_TEMPLATE_COVER_MOVEMENT}": "{verb} {entity_id} um {reason}. Neue Position: {position}%.",
        }

        with (
            patch.object(ha_entity_registry, "async_get", return_value=mock_registry),
            patch(
                "custom_components.smart_cover_automation.coordinator.translation.async_get_translations", new_callable=AsyncMock
            ) as mock_get_translations,
            patch("custom_components.smart_cover_automation.coordinator.async_log_entry") as mock_log_entry,
        ):
            mock_get_translations.return_value = german_translations

            # Execute
            await mock_coordinator._add_logbook_entry_cover_movement(
                verb_key="verb_opening",
                entity_id=MOCK_COVER_ENTITY_ID,
                reason_key="reason_heat_protection",
                target_pos=50,
            )

            # Verify German translation was used
            assert mock_log_entry.call_count == 1
            message = mock_log_entry.call_args.kwargs["message"]
            assert "Öffne" in message
            assert "vor Hitze zu schützen" in message
            assert "Neue Position" in message
