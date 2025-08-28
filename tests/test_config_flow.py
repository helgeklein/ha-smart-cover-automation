"""Tests for the Smart Cover Automation config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation.config_flow import FlowHandler
from custom_components.smart_cover_automation.const import (
    AUTOMATION_TYPE_SUN,
    AUTOMATION_TYPE_TEMPERATURE,
    CONF_AUTOMATION_TYPE,
    CONF_COVERS,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
)

from .conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2


class TestConfigFlow:
    """Test config flow."""

    @pytest.fixture
    def flow_handler(self) -> FlowHandler:
        """Create a flow handler."""
        return FlowHandler()

    @pytest.fixture
    def mock_hass_with_covers(self) -> MagicMock:
        """Create mock hass with cover entities."""
        hass = MagicMock()
        hass.states.get.side_effect = lambda entity_id: (
            MagicMock(state="closed") if entity_id.startswith("cover.") else None
        )
        return hass

    async def test_user_step_temperature_success(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test successful temperature automation setup."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            CONF_COVERS: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            CONF_AUTOMATION_TYPE: AUTOMATION_TYPE_TEMPERATURE,
            CONF_MAX_TEMP: 25.0,
            CONF_MIN_TEMP: 20.0,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == user_input
        assert "2 covers" in result["title"]

    async def test_user_step_sun_success(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test successful sun automation setup."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            CONF_COVERS: [MOCK_COVER_ENTITY_ID],
            CONF_AUTOMATION_TYPE: AUTOMATION_TYPE_SUN,
            CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
            CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)

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
            CONF_COVERS: ["cover.nonexistent"],
            CONF_AUTOMATION_TYPE: AUTOMATION_TYPE_TEMPERATURE,
        }

        result = await flow_handler.async_step_user(user_input)

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
            CONF_COVERS: [MOCK_COVER_ENTITY_ID],
            CONF_AUTOMATION_TYPE: AUTOMATION_TYPE_TEMPERATURE,
            CONF_MAX_TEMP: 20.0,  # Less than min_temp
            CONF_MIN_TEMP: 25.0,
        }

        result = await flow_handler.async_step_user(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_temperature_range"

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
            CONF_COVERS: [MOCK_COVER_ENTITY_ID],
            CONF_AUTOMATION_TYPE: AUTOMATION_TYPE_TEMPERATURE,
            CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
            CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)

        # Should still succeed but log warning
        assert result["type"] == FlowResultType.CREATE_ENTRY

    async def test_user_step_show_form_no_input(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test showing form when no input provided."""
        result = await flow_handler.async_step_user(None)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert CONF_COVERS in result["data_schema"].schema
        assert CONF_AUTOMATION_TYPE in result["data_schema"].schema

    async def test_user_step_configuration_error(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test handling of configuration validation errors."""
        flow_handler.hass = mock_hass_with_covers

        # Create malformed input that will cause KeyError
        user_input = {
            CONF_COVERS: [MOCK_COVER_ENTITY_ID],
            # Missing CONF_AUTOMATION_TYPE intentionally
        }

        result = await flow_handler.async_step_user(user_input)

        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_config"

    async def test_unique_id_generation(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test unique ID generation based on covers."""
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            CONF_COVERS: [MOCK_COVER_ENTITY_ID_2, MOCK_COVER_ENTITY_ID],  # Unsorted
            CONF_AUTOMATION_TYPE: AUTOMATION_TYPE_TEMPERATURE,
            CONF_MAX_TEMP: DEFAULT_MAX_TEMP,
            CONF_MIN_TEMP: DEFAULT_MIN_TEMP,
        }

        with (
            patch.object(flow_handler, "async_set_unique_id") as mock_set_id,
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            await flow_handler.async_step_user(user_input)

            # Should use sorted cover list for unique ID
            expected_id = "_".join(sorted(user_input[CONF_COVERS]))
            mock_set_id.assert_called_once_with(expected_id)

    async def test_version_and_domain(
        self,
        flow_handler: FlowHandler,
    ) -> None:
        """Test flow version and domain."""
        assert flow_handler.VERSION == 1
        assert flow_handler.domain == DOMAIN
