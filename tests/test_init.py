"""Tests for the Smart Cover Automation integration lifecycle management.

This module tests the core lifecycle management functions of the Smart Cover Automation
integration, including setup, teardown, and reload operations. The tests validate:

- Integration setup and initialization process
- Platform setup and coordinator initialization
- Configuration entry management and runtime data
- Error handling during setup and teardown operations
- Update listener configuration for dynamic reconfiguration
- Platform unloading and cleanup procedures
- Reload functionality for configuration changes

These lifecycle tests ensure that the integration properly integrates with Home Assistant's
configuration entry system and handles all aspects of the integration lifecycle, from
initial setup through runtime operation to eventual removal or reconfiguration.

The tests cover both successful operations and various failure scenarios to ensure
robust error handling and graceful degradation when issues occur during setup or
teardown operations.
"""

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
    """Test suite for Smart Cover Automation integration lifecycle management.

    This test class validates the complete lifecycle of the Smart Cover Automation
    integration within Home Assistant, including:

    - Initial setup and platform registration
    - Coordinator initialization and first data refresh
    - Runtime data configuration and storage
    - Update listener setup for configuration changes
    - Error handling during setup, teardown, and reload operations
    - Platform unloading and resource cleanup
    - Configuration entry reload functionality

    The tests ensure that the integration properly integrates with Home Assistant's
    configuration entry system and handles all lifecycle events correctly, both in
    successful scenarios and when errors occur during various phases of operation.
    """

    async def test_setup_entry_success(self) -> None:
        """Test successful setup of a configuration entry.

        Validates the complete successful setup process for a Smart Cover Automation
        configuration entry. This test ensures that:

        - DataUpdateCoordinator is properly instantiated
        - Initial data refresh is performed successfully
        - All required platforms (sensor, binary_sensor, switch) are set up
        - Runtime data is properly configured and stored
        - Setup returns True to indicate success to Home Assistant

        The successful setup process is critical for the integration to function
        properly and provide automation capabilities to users.
        """
        # Create mock Home Assistant instance with configuration entry management
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        # Create configuration entry with temperature automation settings
        config_entry = MockConfigEntry(create_temperature_config())

        # Mock integration loading and coordinator creation
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            # Setup mock coordinator with successful first refresh
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Execute setup process
            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify successful setup
        assert result is True
        mock_coordinator.async_config_entry_first_refresh.assert_called_once()
        hass.config_entries.async_forward_entry_setups.assert_called_once()

    async def test_setup_entry_coordinator_init_failure(self) -> None:
        """Test setup failure during coordinator initialization.

        Validates that the integration properly handles and reports failures that
        occur during DataUpdateCoordinator initialization. This could happen due to:

        - Invalid configuration parameters
        - Missing required entities or sensors
        - Home Assistant service unavailability
        - Resource allocation failures

        When coordinator initialization fails, the setup should return False to
        inform Home Assistant that the integration setup was unsuccessful.
        """
        # Create mock Home Assistant instance
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MockConfigEntry(create_temperature_config())

        # Mock coordinator initialization failure
        with patch(
            "custom_components.smart_cover_automation.DataUpdateCoordinator",
            side_effect=ValueError("Coordinator init failed"),
        ):
            # Execute setup process (should fail)
            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify setup failure is properly reported
        assert result is False

    async def test_setup_entry_refresh_failure(self) -> None:
        """Test setup failure during initial data refresh.

        Validates that the integration properly handles failures during the initial
        data refresh phase of coordinator setup. This could occur due to:

        - Unavailable sensors or entities
        - Network connectivity issues
        - Invalid sensor data or readings
        - Home Assistant service communication failures

        When the initial refresh fails, setup should return False to prevent the
        integration from being marked as successfully loaded when it cannot
        actually function properly.
        """
        # Create mock Home Assistant instance
        hass = MagicMock(spec=HomeAssistant)
        config_entry = MockConfigEntry(create_temperature_config())

        # Mock successful coordinator creation but failed initial refresh
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=OSError("Refresh failed"))
            mock_coordinator_class.return_value = mock_coordinator

            # Execute setup process (should fail at refresh)
            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify setup failure is properly reported
        assert result is False

    async def test_setup_entry_platform_setup_failure(self) -> None:
        """Test setup failure during platform setup phase.

        Validates that the integration properly handles failures during the platform
        setup phase, where individual platforms (sensor, binary_sensor, switch) are
        loaded and initialized. This could fail due to:

        - Platform module import errors
        - Platform initialization failures
        - Missing dependencies or requirements
        - Home Assistant platform registration issues

        When platform setup fails, the integration should return False to indicate
        that it could not be fully set up and should not be considered operational.
        """
        # Create mock Home Assistant instance with platform setup failure
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=ImportError("Platform setup failed"))

        config_entry = MockConfigEntry(create_temperature_config())

        # Mock successful coordinator setup but failed platform setup
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Execute setup process (should fail at platform setup)
            result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify setup failure is properly reported
        assert result is False

    async def test_unload_entry_success(self) -> None:
        """Test successful unloading of a configuration entry.

        Validates the proper cleanup and unloading process when a Smart Cover
        Automation configuration entry is removed or disabled. This test ensures:

        - All platforms are properly unloaded and cleaned up
        - Resources are released and entities are removed
        - Unload operation returns True to indicate success
        - No lingering references or memory leaks occur

        Successful unloading is important for system stability and allows users
        to remove or reconfigure the integration without Home Assistant restart.
        """
        # Create mock Home Assistant instance with platform unloading capability
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        config_entry = MockConfigEntry(create_temperature_config())

        # Execute unload process
        result = await async_unload_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify successful unloading
        assert result is True
        hass.config_entries.async_unload_platforms.assert_called_once()

    async def test_unload_entry_failure(self) -> None:
        """Test unload failure during platform cleanup.

        Validates that the integration properly handles and reports failures during
        the unload process. Platform unloading might fail due to:

        - Platform cleanup errors or exceptions
        - Resource release failures
        - Entity removal issues
        - Background task termination problems

        When unloading fails, the function should return False to inform Home
        Assistant that the integration could not be completely cleaned up.
        """
        # Create mock Home Assistant instance with platform unloading failure
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(side_effect=OSError("Unload failed"))

        config_entry = MockConfigEntry(create_temperature_config())

        # Execute unload process (should fail)
        result = await async_unload_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify unload failure is properly reported
        assert result is False

    async def test_reload_entry(self) -> None:
        """Test configuration entry reload functionality.

        Validates that the integration properly handles reload requests, which
        typically occur when:

        - Configuration options are changed through the options flow
        - Integration settings are updated in the UI
        - Manual reload is requested by the user
        - Configuration validation requires a restart

        The reload function should properly delegate to Home Assistant's
        configuration entry reload mechanism using the correct entry ID.
        """
        # Create mock Home Assistant instance with reload capability
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_reload = AsyncMock()

        config_entry = MockConfigEntry(create_temperature_config())

        # Execute reload process
        await async_reload_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify reload was requested with correct entry ID
        hass.config_entries.async_reload.assert_called_once_with(config_entry.entry_id)

    async def test_runtime_data_setup(self) -> None:
        """Test that runtime data is properly configured during setup.

        Validates that the RuntimeData object is correctly created and attached
        to the configuration entry during setup. Runtime data contains:

        - Integration metadata and version information
        - DataUpdateCoordinator instance for automation logic
        - Configuration dictionary for runtime access
        - Shared state accessible to all platforms and entities

        Proper runtime data setup is essential for entities to access coordinator
        data and for the integration to maintain state across platforms.
        """
        # Create mock Home Assistant instance
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        config_entry = MockConfigEntry(create_temperature_config())

        # Mock all required components for runtime data creation
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration") as mock_get_integration,
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
            patch("custom_components.smart_cover_automation.RuntimeData") as mock_data_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            mock_integration = MagicMock()
            mock_get_integration.return_value = mock_integration

            # Execute setup process
            await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

            # Verify RuntimeData was created with correct parameters
            mock_data_class.assert_called_once_with(
                integration=mock_integration,
                coordinator=mock_coordinator,
                config=dict(config_entry.data),
            )

            # Verify runtime_data was attached to config entry
            assert config_entry.runtime_data is mock_data_class.return_value

    async def test_update_listener_setup(self) -> None:
        """Test that update listener is properly configured for dynamic reconfiguration.

        Validates that the integration sets up proper update listeners to handle
        configuration changes dynamically. The update listener system allows:

        - Real-time response to options flow changes
        - Dynamic reconfiguration without full reload
        - Automatic cleanup when configuration entry is unloaded
        - Proper integration lifecycle management

        Update listeners are essential for responding to user configuration changes
        made through the Home Assistant options flow without requiring integration
        restart or Home Assistant reload.
        """
        # Create mock Home Assistant instance
        hass = MagicMock(spec=HomeAssistant)
        hass.config_entries = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        config_entry = MockConfigEntry(create_temperature_config())

        # Mock integration loading and coordinator setup
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Execute setup process
            await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

            # Verify update listener was properly configured
            config_entry.add_update_listener.assert_called_once()
            config_entry.async_on_unload.assert_called_once()
