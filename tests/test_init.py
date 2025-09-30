"""Tests for Smart Cover Automation integration setup, teardown, and lifecycle management.

This module contains comprehensive tests for the core integration functionality
that manages the integration's lifecycle within Home Assistant. The tests focus
on the critical setup and teardown processes that handle configuration entry
management, coordinator initialization, and platform registration.

Key testing areas include:
1. **Configuration Entry Setup**: Tests successful integration loading and
   initialization of the DataUpdateCoordinator with proper platform setup
2. **Error Handling During Setup**: Tests graceful failure handling when
   coordinator initialization, data refresh, or platform setup fails
3. **Configuration Entry Unloading**: Tests proper cleanup and resource
   release when the integration is disabled or removed
4. **Configuration Entry Reloading**: Tests configuration reload functionality
   when settings are changed through the options flow

The integration lifecycle is critical because it:
- Establishes the foundation for all automation functionality
- Manages resource allocation and cleanup to prevent memory leaks
- Ensures proper integration with Home Assistant's configuration system
- Provides error handling and recovery for various failure scenarios

These tests ensure that the integration properly integrates with Home Assistant's
configuration entry system and handles all lifecycle events correctly, both in
successful scenarios and when errors occur during various phases of operation.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smart_cover_automation import (
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


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

    async def test_setup_entry_success(self, mock_hass_with_spec, mock_config_entry_basic) -> None:
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
        # Create mock Home Assistant instance with successful platform setup
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

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
            result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify successful setup
        assert result is True
        mock_coordinator.async_config_entry_first_refresh.assert_called_once()
        mock_hass_with_spec.config_entries.async_forward_entry_setups.assert_called_once()

    @pytest.mark.parametrize(
        "failure_point, exception_type, exception_message, mock_setup",
        [
            (
                "coordinator_init",
                ValueError,
                "Coordinator init failed",
                lambda mock_hass, mock_entry: patch(
                    "custom_components.smart_cover_automation.DataUpdateCoordinator",
                    side_effect=ValueError("Coordinator init failed"),
                ),
            ),
            (
                "coordinator_refresh",
                OSError,
                "Refresh failed",
                lambda mock_hass, mock_entry: (
                    patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
                    patch("custom_components.smart_cover_automation.DataUpdateCoordinator"),
                ),
            ),
            (
                "platform_setup",
                ImportError,
                "Platform setup failed",
                lambda mock_hass, mock_entry: (
                    patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
                    patch("custom_components.smart_cover_automation.DataUpdateCoordinator"),
                ),
            ),
        ],
    )
    async def test_setup_entry_failures(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
        failure_point: str,
        exception_type: type,
        exception_message: str,
        mock_setup,
    ) -> None:
        """Test setup failures at different points in the process.

        This parametrized test validates that the integration properly handles and reports
        failures that can occur at various stages of the setup process:

        - Coordinator initialization failures
        - Initial data refresh failures
        - Platform setup failures

        Each failure type represents a different category of setup issues that could
        prevent the integration from functioning properly.
        """
        if failure_point == "coordinator_init":
            # Mock coordinator initialization failure
            with mock_setup(mock_hass_with_spec, mock_config_entry_basic):
                result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        elif failure_point == "coordinator_refresh":
            # Mock successful coordinator creation but failed initial refresh
            patches = mock_setup(mock_hass_with_spec, mock_config_entry_basic)
            with patches[0], patches[1] as mock_coordinator_class:
                mock_coordinator = MagicMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=exception_type(exception_message))
                mock_coordinator_class.return_value = mock_coordinator

                result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        else:  # failure_point == "platform_setup"
            # Mock successful coordinator setup but failed platform setup
            mock_hass_with_spec.config_entries = MagicMock()
            mock_hass_with_spec.config_entries.async_forward_entry_setups = AsyncMock(side_effect=exception_type(exception_message))

            patches = mock_setup(mock_hass_with_spec, mock_config_entry_basic)
            with patches[0], patches[1] as mock_coordinator_class:
                mock_coordinator = MagicMock()
                mock_coordinator.async_config_entry_first_refresh = AsyncMock()
                mock_coordinator_class.return_value = mock_coordinator

                result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify setup failure is properly reported for all scenarios
        assert result is False

    @pytest.mark.parametrize(
        "unload_success, expected_result",
        [
            (True, True),  # Successful unload
            (False, False),  # Failed unload
        ],
    )
    async def test_unload_entry_scenarios(
        self, mock_hass_with_spec, mock_config_entry_basic, unload_success: bool, expected_result: bool
    ) -> None:
        """Test unload entry with different success/failure scenarios.

        This parametrized test validates both successful and failed unload scenarios
        to ensure the integration properly handles platform cleanup in all cases.
        """
        # Create mock Home Assistant instance with platform unloading capability
        mock_hass_with_spec.config_entries = MagicMock()

        if unload_success:
            mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        else:
            mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(side_effect=OSError("Unload failed"))

        # Execute unload process
        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify expected result
        assert result == expected_result
        mock_hass_with_spec.config_entries.async_unload_platforms.assert_called_once()

    async def test_unload_entry_failure(self, mock_hass_with_spec, mock_config_entry_basic) -> None:
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
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(side_effect=OSError("Unload failed"))

        # Execute unload process (should fail)
        result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify unload failure is properly reported
        assert result is False

    async def test_reload_entry(self, mock_hass_with_spec, mock_config_entry_basic) -> None:
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
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload process
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify reload was requested with correct entry ID
        mock_hass_with_spec.config_entries.async_reload.assert_called_once_with(mock_config_entry_basic.entry_id)

    async def test_runtime_data_setup(self, mock_hass_with_spec, mock_config_entry_basic) -> None:
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
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

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
            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

            # Verify RuntimeData was created with correct parameters
            mock_data_class.assert_called_once_with(
                integration=mock_integration,
                coordinator=mock_coordinator,
                config=dict(mock_config_entry_basic.data),
            )

            # Verify runtime_data was attached to config entry
            assert mock_config_entry_basic.runtime_data is mock_data_class.return_value

    async def test_update_listener_setup(self, mock_hass_with_spec, mock_config_entry_basic) -> None:
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
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

        # Mock integration loading and coordinator setup
        with (
            patch("custom_components.smart_cover_automation.async_get_loaded_integration"),
            patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class,
        ):
            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Execute setup process
            await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

            # Verify update listener was properly configured
            mock_config_entry_basic.add_update_listener.assert_called_once()
            mock_config_entry_basic.async_on_unload.assert_called_once()
