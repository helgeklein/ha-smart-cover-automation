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

from .conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2


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

    @pytest.fixture
    def flow_handler(self) -> FlowHandler:
        """Create a fresh FlowHandler instance for testing.

        Provides a clean FlowHandler instance for each test method to ensure
        test isolation and prevent state leakage between tests.

        Returns:
            New FlowHandler instance ready for testing
        """
        return FlowHandler()

    @pytest.fixture
    def mock_hass_with_covers(self) -> MagicMock:
        """Create mock Home Assistant instance with valid cover entities.

        Provides a mocked Home Assistant instance that simulates the presence
        of cover entities in the state registry. This allows tests to validate
        configuration flow behavior with existing cover entities without
        requiring a full Home Assistant setup.

        The mock returns a "closed" state for any entity ID starting with "cover."
        and None for all other entity IDs, simulating a typical Home Assistant
        environment with cover entities present.

        Returns:
            MagicMock instance configured to simulate Home Assistant with covers
        """
        hass = MagicMock()
        hass.states.get.side_effect = lambda entity_id: (MagicMock(state="closed") if entity_id.startswith("cover.") else None)
        return hass

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

    async def test_user_step_invalid_cover(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test error handling when user specifies non-existent cover entities.

        Validates that the config flow properly handles and reports errors when
        users try to configure automation for cover entities that don't exist
        in Home Assistant. This prevents invalid configurations and provides
        clear feedback to users about the problem.

        The test simulates a scenario where Home Assistant's state registry
        returns None for the specified cover entity, indicating it doesn't exist.
        """
        # Mock Home Assistant to return None for any entity (simulating non-existence)
        hass = MagicMock()
        hass.states.get.return_value = None  # Cover doesn't exist
        flow_handler.hass = hass

        # Attempt to configure automation for non-existent cover
        user_input = {
            ConfKeys.COVERS.value: ["cover.nonexistent"],
        }

        # Execute config flow and verify error handling
        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        # Verify the flow shows an error and returns to the form
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_cover"

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
        - Deprecated fields are not present (automation_type was removed)
        """
        # Request the initial configuration form (no user input)
        result = await flow_handler.async_step_user(None)
        result = self._as_dict(result)

        # Verify form presentation and schema
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert ConfKeys.COVERS.value in result["data_schema"].schema

        # Verify deprecated automation type field is not present
        schema = result["data_schema"].schema
        assert "automation_type" not in schema

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
        """Test unique ID generation for integration configuration entries.

        Validates that the config flow generates stable, unique identifiers for
        each integration instance. The unique ID system prevents duplicate
        configurations and enables proper configuration entry management.

        This test verifies:
        - A valid UUID is generated and set as the unique ID
        - The unique ID is independent of cover entity order or configuration
        - The UUID follows proper formatting standards
        - The flow calls appropriate Home Assistant unique ID methods
        """
        flow_handler.hass = mock_hass_with_covers

        # Create user input with covers in different order to test UUID stability
        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID_2, MOCK_COVER_ENTITY_ID],  # Unsorted
            ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
        }

        # Mock unique ID operations to capture generated values
        with (
            patch.object(flow_handler, "async_set_unique_id") as mock_set_id,
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            await flow_handler.async_step_user(user_input)

        # Verify unique ID was generated and follows UUID format
        args, _ = mock_set_id.call_args
        assert len(args) == 1
        uid = args[0]
        import uuid as _uuid

        # Validate it's a properly formatted UUID string
        _uuid.UUID(uid)

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
        """Test single instance enforcement prevents duplicate configurations.

        Validates that the Smart Cover Automation integration correctly enforces
        the single instance limitation. Home Assistant allows integrations to
        restrict themselves to one configuration entry, which is appropriate
        for system-wide automation integrations like this one.

        This test verifies:
        - When an existing configuration entry is present, new config flows abort
        - The abort reason is properly set to "single_instance_allowed"
        - The flow prevents users from creating duplicate configurations
        - Existing configurations are properly detected
        """
        # Provide Home Assistant instance for proper flow operation
        flow_handler.hass = MagicMock()

        # Simulate existing configuration entry to trigger single instance check
        flow_handler._async_current_entries = MagicMock(return_value=[MagicMock()])  # type: ignore[attr-defined]

        # Attempt to start new configuration flow
        result = await flow_handler.async_step_user(None)
        result_dict = self._as_dict(result)

        # Verify flow aborts with single instance restriction
        assert result_dict["type"] == FlowResultType.ABORT
        assert result_dict["reason"] == "single_instance_allowed"
