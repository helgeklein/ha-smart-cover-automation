"""Tests for Smart Cover Automation unload service cleanup.

This module tests the service removal logic when the integration is unloaded,
including cleanup of coordinator references and service deregistration.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.smart_cover_automation import async_setup_entry, async_unload_entry
from custom_components.smart_cover_automation.const import (
    DATA_COORDINATORS,
    DOMAIN,
    SERVICE_LOGBOOK_ENTRY,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import MockConfigEntry, create_temperature_config


class TestUnloadServiceCleanup:
    """Test suite for service cleanup during integration unload."""

    async def test_unload_removes_coordinator_reference(self, mock_hass_with_spec) -> None:
        """Test that unload removes the coordinator from hass.data."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        # Setup the integration first
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        # Verify coordinator was added
        assert mock_config_entry.entry_id in mock_hass_with_spec.data[DOMAIN][DATA_COORDINATORS]

        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        # Unload the integration
        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        assert result is True
        # Verify coordinator was removed (entire domain was cleaned up since it was empty)
        assert DOMAIN not in mock_hass_with_spec.data or mock_config_entry.entry_id not in mock_hass_with_spec.data.get(DOMAIN, {}).get(
            DATA_COORDINATORS, {}
        )

    async def test_unload_cleans_up_empty_coordinator_dict(self, mock_hass_with_spec) -> None:
        """Test that unload removes DATA_COORDINATORS dict when empty."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        assert result is True
        # Verify DATA_COORDINATORS was removed (entire domain cleaned up when empty)
        assert DOMAIN not in mock_hass_with_spec.data or DATA_COORDINATORS not in mock_hass_with_spec.data.get(DOMAIN, {})

    async def test_unload_cleans_up_empty_domain_data(self, mock_hass_with_spec) -> None:
        """Test that unload removes DOMAIN from hass.data when empty."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        assert result is True
        # Verify DOMAIN was removed from hass.data when it became empty
        assert DOMAIN not in mock_hass_with_spec.data

    async def test_unload_removes_service_when_last_coordinator(self, mock_hass_with_spec) -> None:
        """Test that service is removed when unloading the last coordinator."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        # Mock that service exists
        mock_hass_with_spec.services.has_service = MagicMock(return_value=True)
        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        assert result is True
        # Verify service was removed
        mock_hass_with_spec.services.async_remove.assert_called_once_with(DOMAIN, SERVICE_LOGBOOK_ENTRY)

    async def test_unload_keeps_service_when_other_coordinators_exist(self, mock_hass_with_spec) -> None:
        """Test that service is kept when other coordinators still exist."""
        mock_config_entry1 = MockConfigEntry(create_temperature_config())
        mock_config_entry1.entry_id = "entry_1"
        mock_config_entry2 = MockConfigEntry(create_temperature_config())
        mock_config_entry2.entry_id = "entry_2"

        # Setup two integrations
        for entry in [mock_config_entry1, mock_config_entry2]:
            with (
                patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
                patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            ):
                mock_coordinator = MagicMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                # For the second entry, simulate service already exists
                if entry == mock_config_entry2:
                    mock_hass_with_spec.services.has_service = MagicMock(return_value=True)

                await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, entry))

        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        # Unload only the first entry
        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry1))

        assert result is True
        # Verify service was NOT removed (because entry_2 still exists)
        mock_hass_with_spec.services.async_remove.assert_not_called()
        # Verify second coordinator still exists
        assert mock_config_entry2.entry_id in mock_hass_with_spec.data[DOMAIN][DATA_COORDINATORS]

    async def test_unload_handles_missing_domain_data(self, mock_hass_with_spec) -> None:
        """Test that unload handles missing domain data gracefully."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        # Setup without domain data in hass.data
        mock_hass_with_spec.data = {}
        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        # Should still succeed even with no domain data
        assert result is True

    async def test_unload_handles_missing_coordinators_dict(self, mock_hass_with_spec) -> None:
        """Test that unload handles missing coordinators dict gracefully."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        # Setup with domain data but no coordinators dict
        mock_hass_with_spec.data[DOMAIN] = {}
        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        assert result is True

    async def test_unload_preserves_other_domain_data(self, mock_hass_with_spec) -> None:
        """Test that unload preserves other data in the domain dict."""
        mock_config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        # Add some other data to the domain
        mock_hass_with_spec.data[DOMAIN]["other_data"] = "should_be_preserved"
        # Mock platform unloading
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry))

        assert result is True
        # Verify DOMAIN still exists because it has other data
        assert DOMAIN in mock_hass_with_spec.data
        assert mock_hass_with_spec.data[DOMAIN]["other_data"] == "should_be_preserved"
        # But coordinators should be removed
        assert DATA_COORDINATORS not in mock_hass_with_spec.data[DOMAIN]
