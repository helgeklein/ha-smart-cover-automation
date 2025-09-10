"""Tests for the Smart Cover Automation config flow."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys
from custom_components.smart_cover_automation.config_flow import FlowHandler
from custom_components.smart_cover_automation.const import DOMAIN

from .conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2


class TestConfigFlow:
    """Test config flow."""

    @staticmethod
    def _as_dict(result: object) -> dict[str, Any]:
        """Loosen HA's ConfigFlowResult typing for test assertions."""
        return cast(dict[str, Any], result)

    @pytest.fixture
    def flow_handler(self) -> FlowHandler:
        """Create a flow handler."""
        return FlowHandler()

    @pytest.fixture
    def mock_hass_with_covers(self) -> MagicMock:
        """Create mock hass with cover entities."""
        hass = MagicMock()
        hass.states.get.side_effect = lambda entity_id: (MagicMock(state="closed") if entity_id.startswith("cover.") else None)
        return hass

    async def test_user_step_combined_success_with_temps(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test successful setup; combined mode is always used."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            ConfKeys.MAX_TEMPERATURE.value: 25.0,
            ConfKeys.MIN_TEMPERATURE.value: 20.0,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)
            result = self._as_dict(result)
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["data"] == user_input
            assert "2 covers" in result["title"]

    async def test_user_step_combined_success_without_temps(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test successful setup without temperature fields."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.MAX_TEMPERATURE.value: CONF_SPECS[ConfKeys.MAX_TEMPERATURE].default,
            ConfKeys.MIN_TEMPERATURE.value: CONF_SPECS[ConfKeys.MIN_TEMPERATURE].default,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)
            result = self._as_dict(result)
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["data"] == user_input

    async def test_user_step_invalid_cover(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test error when cover entity doesn't exist."""
        hass = MagicMock()
        hass.states.get.return_value = None  # Cover doesn't exist
        flow_handler.hass = hass

        user_input = {
            ConfKeys.COVERS.value: ["cover.nonexistent"],
        }

        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_cover"

    async def test_user_step_invalid_temperature_range(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test error when max temp <= min temp."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.MAX_TEMPERATURE.value: 20.0,  # Less than min_temp
            ConfKeys.MIN_TEMPERATURE.value: 25.0,
        }

        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_temperature_range"

    async def test_user_step_only_max_temperature_requires_min(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """When only max_temperature is provided, min_temperature should be required with field error."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.MAX_TEMPERATURE.value: 25.0,
            # MIN_TEMPERATURE intentionally omitted
        }

        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        assert result["type"] == FlowResultType.FORM
        # Expect field-specific error on min_temperature
        assert result["errors"][ConfKeys.MIN_TEMPERATURE.value] == "required_with_max_temperature"

    async def test_user_step_only_min_temperature_requires_max(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """When only min_temperature is provided, max_temperature should be required with field error."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.MIN_TEMPERATURE.value: 20.0,
            # MAX_TEMPERATURE intentionally omitted
        }

        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        assert result["type"] == FlowResultType.FORM
        # Expect field-specific error on max_temperature
        assert result["errors"][ConfKeys.MAX_TEMPERATURE.value] == "required_with_min_temperature"

    async def test_user_step_unavailable_cover_warning(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test warning when cover is unavailable but still allows config."""
        hass = MagicMock()
        cover_state = MagicMock()
        cover_state.state = "unavailable"
        hass.states.get.return_value = cover_state
        flow_handler.hass = hass

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.MAX_TEMPERATURE.value: CONF_SPECS[ConfKeys.MAX_TEMPERATURE].default,
            ConfKeys.MIN_TEMPERATURE.value: CONF_SPECS[ConfKeys.MIN_TEMPERATURE].default,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)
            result = self._as_dict(result)

        # Should still succeed but log warning
        assert result["type"] == FlowResultType.CREATE_ENTRY

    async def test_user_step_show_form_no_input(self, flow_handler: FlowHandler) -> None:
        """Test showing form when no input provided."""
        result = await flow_handler.async_step_user(None)
        result = self._as_dict(result)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert ConfKeys.COVERS.value in result["data_schema"].schema
        # No automation type field should be present
        schema = result["data_schema"].schema
        assert "automation_type" not in schema

    async def test_user_step_configuration_error(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test handling of configuration validation errors."""
        flow_handler.hass = mock_hass_with_covers

        # Create malformed input that will cause KeyError (missing covers)
        user_input: dict[str, Any] = {}

        result = await flow_handler.async_step_user(user_input)
        result = self._as_dict(result)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_config"

    async def test_unique_id_generation(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test unique ID generation creates a stable UUID independent of covers."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID_2, MOCK_COVER_ENTITY_ID],  # Unsorted
            ConfKeys.MAX_TEMPERATURE.value: CONF_SPECS[ConfKeys.MAX_TEMPERATURE].default,
            ConfKeys.MIN_TEMPERATURE.value: CONF_SPECS[ConfKeys.MIN_TEMPERATURE].default,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id") as mock_set_id,
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            await flow_handler.async_step_user(user_input)

        # Ensure a UUID-like value was used
        args, _ = mock_set_id.call_args
        assert len(args) == 1
        uid = args[0]
        import uuid as _uuid

        # Validate it's a valid UUID string
        _uuid.UUID(uid)

    async def test_version_and_domain(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test flow version and domain."""
        assert flow_handler.VERSION == 1
        assert flow_handler.domain == DOMAIN
