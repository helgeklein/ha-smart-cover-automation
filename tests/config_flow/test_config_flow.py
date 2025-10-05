"""Tests for the Smart Cover Automation config flow.

This module tests the Home Assistant configuration flow that allows users to set up
the Smart Cover Automation integration through the UI. The config flow handles:
- User input validation for cover entities and configuration parameters
- Error handling for invalid configurations
- Unique ID generation to prevent duplicate installations
- Single instance enforcement (only one automation can be configured)

The tests cover various user input scenarios including:
- Successful configuration with valid inputs
- Error handling for invalid cover entities
- Warning handling for unavailable cover entities
- Configuration validation and error reporting
- Single instance enforcement and abort conditions
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys
from custom_components.smart_cover_automation.config_flow import FlowHandler
from custom_components.smart_cover_automation.const import DOMAIN, INTEGRATION_NAME

from ..conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2


class TestConfigFlow:
    """Test class for the Smart Cover Automation configuration flow.

    This test class validates the configuration flow functionality including:
    - Form presentation and user input handling
    - Validation of cover entities and configuration parameters
    - Error handling and user feedback
    - Successful configuration entry creation
    - Integration lifecycle management (unique IDs, single instance)
    """

    @staticmethod
    def _as_dict(result: object) -> dict[str, Any]:
        """Convert Home Assistant ConfigFlowResult to dictionary for test assertions.

        Home Assistant's config flow results have strict typing that can make
        test assertions verbose. This helper loosens the typing to allow easier
        dictionary-style access to result properties in tests.

        Args:
            result: ConfigFlowResult object from Home Assistant

        Returns:
            Dictionary representation of the result for easier testing
        """
        return cast(dict[str, Any], result)

    async def test_user_step_combined_success_with_temps(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test successful configuration flow completion with temperature automation.

        Validates the happy path where a user provides valid configuration including:
        - Multiple cover entities that exist in Home Assistant
        - Custom temperature threshold value

        The test verifies that:
        - The flow completes successfully (CREATE_ENTRY result)
        - User input is preserved in the configuration data
        - The integration title is set correctly
        - Unique ID handling is properly mocked to prevent actual UUID operations
        """
        flow_handler.hass = mock_hass_with_covers

        # Create user input with multiple covers and custom temperature threshold
        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            ConfKeys.TEMP_THRESHOLD.value: 25.0,
        }

        # Mock unique ID operations to prevent actual UUID generation during tests
        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            # Execute the configuration flow with user input
            result = await flow_handler.async_step_user(user_input)
            result = self._as_dict(result)

            # Verify successful configuration entry creation
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["data"] == user_input
            assert result["title"] == INTEGRATION_NAME

    async def test_user_step_combined_success_without_temps(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test successful configuration flow with default temperature values.

        Validates the configuration flow when users provide minimal input:
        - Single cover entity
        - Default temperature threshold (uses config spec default)

        This tests the common use case where users accept default settings
        and only specify the covers they want to automate.
        """
        flow_handler.hass = mock_hass_with_covers

        # Create minimal user input with default temperature threshold
        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
        }

        # Mock unique ID operations and execute configuration flow
        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)
            result = self._as_dict(result)

            # Verify successful configuration with default values
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["data"] == user_input

    @pytest.mark.parametrize(
        "mock_setup,user_input,expected_error,test_description",
        [
            # Test invalid/non-existent cover
            (
                lambda flow_handler: setattr(flow_handler, "hass", MagicMock(states=MagicMock(get=MagicMock(return_value=None)))),
                {ConfKeys.COVERS.value: ["cover.nonexistent"]},
                "invalid_cover",
                "non-existent cover entity",
            ),
            # Test malformed configuration (missing required covers field)
            (
                lambda flow_handler: setattr(flow_handler, "hass", MagicMock()),
                {},
                "invalid_config",
                "missing required covers field",
            ),
            # Test empty covers list
            (
                lambda flow_handler: setattr(flow_handler, "hass", MagicMock()),
                {ConfKeys.COVERS.value: []},
                "invalid_config",
                "empty covers list",
            ),
        ],
    )
    async def test_config_flow_error_scenarios_parametrized(
        self, mock_setup, user_input: dict[str, Any], expected_error: str, test_description: str, flow_handler: FlowHandler
    ) -> None:
        """Test various configuration flow error scenarios.

        This parametrized test validates that the config flow properly handles and reports
        different types of configuration errors, ensuring robust error handling and
        preventing invalid configurations from being created.

        Test scenarios include:
        - Non-existent cover entities
        - Malformed configuration data
        - Empty or invalid field values
        """
        # Apply the mock setup for this scenario
        mock_setup(flow_handler)

        # Execute config flow with the test input
        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        # Verify error handling returns to form with appropriate error message
        assert result["type"] == FlowResultType.FORM, f"Expected FORM result for {test_description}"
        assert result["errors"]["base"] == expected_error, f"Expected {expected_error} error for {test_description}"

    async def test_user_step_unavailable_cover_warning(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test handling of unavailable cover entities during configuration.

        Validates that the config flow handles unavailable cover entities gracefully.
        Cover entities may be temporarily unavailable due to network issues, device
        problems, or other transient conditions. The flow should allow configuration
        to proceed (since the entity exists) while logging appropriate warnings.

        This test simulates a cover entity that exists in Home Assistant but is
        currently in an "unavailable" state, which is different from non-existent.
        """
        # Mock Home Assistant with an unavailable cover entity
        hass = MagicMock()
        cover_state = MagicMock()
        cover_state.state = "unavailable"  # Entity exists but is unavailable
        hass.states.get.return_value = cover_state
        flow_handler.hass = hass

        # Configure automation for the unavailable cover
        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
        }

        # Mock unique ID operations and execute configuration flow
        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)
            result = self._as_dict(result)

        # Configuration should still succeed despite unavailable entity
        # The integration will handle unavailable entities at runtime
        assert result["type"] == FlowResultType.CREATE_ENTRY

    async def test_user_step_show_form_no_input(self, flow_handler: FlowHandler) -> None:
        """Test initial form presentation when no user input is provided.

        Validates that the config flow presents the correct form to users when
        they first access the integration setup page. This tests the initial
        state of the configuration flow before any user interaction.

        The test verifies:
        - The correct form is displayed (FORM result type)
        - The form has the expected step ID ("user")
        - Required fields are present in the form schema
        """
        # Request the initial configuration form (no user input)
        result = await flow_handler.async_step_user(None)
        result = self._as_dict(result)

        # Verify form presentation and schema
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert ConfKeys.COVERS.value in result["data_schema"].schema

    async def test_user_step_configuration_error(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test handling of malformed configuration data.

        Validates that the config flow properly handles and reports errors when
        users provide invalid or incomplete configuration data. This ensures
        robust error handling and prevents the integration from being configured
        with invalid parameters that could cause runtime failures.

        The test simulates malformed input (missing required covers field) to
        trigger configuration validation errors.
        """
        flow_handler.hass = mock_hass_with_covers

        # Create malformed input that will cause validation error (missing required covers field)
        user_input: dict[str, Any] = {}

        # Execute config flow with invalid input
        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        # Verify error handling returns to form with appropriate error message
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_config"

    async def test_unique_id_generation(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test that config flow works properly without requiring unique ID generation.

        Since the integration now uses manifest-based single instance enforcement
        via the 'single_config_entry' property, the config flow itself no longer
        needs to manage unique IDs directly. This test validates that the flow
        operates correctly with this simplified approach.

        This test verifies:
        - Config flow completes successfully without unique ID generation
        - The flow creates entries normally when no duplicate enforcement is needed
        - The configuration validation works as expected
        """
        flow_handler.hass = mock_hass_with_covers

        # Create user input with covers in different order to test stability
        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID_2, MOCK_COVER_ENTITY_ID],  # Unsorted
            ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
        }

        # Execute the config flow
        result = await flow_handler.async_step_user(user_input)
        result_dict = self._as_dict(result)

        # Verify the flow completes successfully
        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        assert result_dict["title"] == "Smart Cover Automation"
        assert result_dict["data"] == user_input

    async def test_version_and_domain(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test configuration flow version and domain metadata.

        Validates that the config flow has the correct version and domain
        identifiers set. These metadata values are used by Home Assistant
        to track configuration schema versions and associate the flow with
        the correct integration domain.

        This ensures:
        - Config flow version matches expected schema version
        - Domain matches the integration's registered domain name
        - Metadata is accessible for Home Assistant's flow management
        """
        # Verify configuration flow metadata
        assert flow_handler.VERSION == 1
        assert flow_handler.domain == DOMAIN

    async def test_single_instance_allowed_abort(self, flow_handler: FlowHandler) -> None:
        """Test single instance enforcement through manifest configuration.

        Validates that the Smart Cover Automation integration uses manifest-based
        single instance enforcement via the 'single_config_entry' property in
        manifest.json. This is the proper Home Assistant way to restrict integrations
        to one configuration entry.

        This test verifies:
        - The config flow itself doesn't need to handle single instance logic
        - The flow operates normally when called directly
        - Single instance enforcement is delegated to Home Assistant's flow manager
        - The manifest.json contains the required 'single_config_entry: true' property
        """
        # Provide Home Assistant instance for proper flow operation
        flow_handler.hass = MagicMock()

        # The config flow should operate normally since single instance enforcement
        # is handled at the manifest level by Home Assistant's flow manager
        result = await flow_handler.async_step_user(None)
        result_dict = self._as_dict(result)

        # Verify flow shows the configuration form normally
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "user"

        # Verify that the manifest.json contains single_config_entry property
        import json
        from pathlib import Path

        manifest_path = Path(__file__).parent.parent.parent / "custom_components" / "smart_cover_automation" / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest.get("single_config_entry") is True, "manifest.json must contain 'single_config_entry: true'"
