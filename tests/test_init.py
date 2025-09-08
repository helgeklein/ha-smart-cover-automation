"""Tests for the Smart Cover Automation integration setup."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation import (
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import MockConfigEntry, create_temperature_config


class TestIntegrationSetup:
    """Test integration setup and teardown."""

    async def test_setup_entry_success(self) -> None:
        """Test successful setup of config entry."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        assert result is True
        mock_coordinator.async_config_entry_first_refresh.assert_called_once()
        hass.config_entries.async_forward_entry_setups.assert_called_once()

    async def test_setup_entry_coordinator_init_failure(self) -> None:
        """Test setup failure during coordinator initialization."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MockConfigEntry(create_temperature_config())

        with patch(
            "custom_components.smart_cover_automation.DataUpdateCoordinator",
            side_effect=ValueError("Coordinator init failed"),
        ):
            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        assert result is False

    async def test_setup_entry_refresh_failure(self) -> None:
        """Test setup failure during initial refresh."""
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=OSError("Refresh failed"))
            mock_coordinator_class.return_value = mock_coordinator

            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        assert result is False

    async def test_setup_entry_platform_setup_failure(self) -> None:
        """Test setup failure during platform setup."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=ImportError("Platform setup failed"))

        config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        assert result is False

    async def test_unload_entry_success(self) -> None:
        """Test successful unload of config entry."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        config_entry = MockConfigEntry(create_temperature_config())

        result = await async_unload_entry(hass, cast(IntegrationConfigEntry, config_entry))

        assert result is True
        hass.config_entries.async_unload_platforms.assert_called_once()

    async def test_unload_entry_failure(self) -> None:
        """Test unload failure."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(side_effect=OSError("Unload failed"))

        config_entry = MockConfigEntry(create_temperature_config())

        result = await async_unload_entry(hass, cast(IntegrationConfigEntry, config_entry))

        assert result is False

    async def test_reload_entry(self) -> None:
        """Test reload of config entry."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_reload = AsyncMock()

        config_entry = MockConfigEntry(create_temperature_config())
        await async_reload_entry(hass, cast(IntegrationConfigEntry, config_entry))

        hass.config_entries.async_reload.assert_called_once_with(config_entry.entry_id)

    async def test_runtime_data_setup(self) -> None:
        """Test that runtime data is properly set up."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration") as mock_get_integration,
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            patch("custom_components.smart_cover_automation.IntegrationData") as mock_data_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            mock_integration = MagicMock()
            mock_get_integration.return_value = mock_integration

            await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

            # Check that IntegrationData was created with correct parameters
            mock_data_class.assert_called_once_with(
                integration=mock_integration,
                coordinator=mock_coordinator,
                config=dict(config_entry.data),
            )

            # Check that runtime_data was set
            assert config_entry.runtime_data is mock_data_class.return_value

    async def test_update_listener_setup(self) -> None:
        """Test that update listener is properly configured."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        config_entry = MockConfigEntry(create_temperature_config())

        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

            # Check that update listener was added
            config_entry.add_update_listener.assert_called_once()
            config_entry.async_on_unload.assert_called_once()
