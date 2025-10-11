"""Tests for Smart Cover Automation smart reload functionality.

This module contains tests for the smart reload feature that optimizes
configuration changes by detecting whether a full reload is needed or if
just refreshing the coordinator is sufficient.

Key testing areas:
1. **Runtime-only changes**: Tests that changes to 'enabled' or 'simulation_mode'
   only trigger a coordinator refresh, not a full reload
2. **Structural changes**: Tests that changes to other configuration keys
   trigger a full reload
3. **Mixed changes**: Tests that if both runtime and structural keys change,
   a full reload is triggered
4. **No changes**: Tests behavior when configuration hasn't changed
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

from custom_components.smart_cover_automation import async_reload_entry
from custom_components.smart_cover_automation.data import IntegrationConfigEntry, RuntimeData


class TestSmartReload:
    """Test suite for smart reload optimization.

    This test class validates that the integration correctly distinguishes between
    configuration changes that require a full reload versus those that can be
    handled with just a coordinator refresh.
    """

    async def test_reload_with_enabled_change_only(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
    ) -> None:
        """Test that changing only 'enabled' triggers coordinator refresh, not full reload.

        When only the 'enabled' flag changes, the integration should:
        - Update the coordinator's merged config
        - Update runtime_data config
        - Trigger a coordinator refresh
        - NOT trigger a full integration reload
        """
        # Setup mock coordinator with old config
        mock_coordinator = MagicMock()
        mock_coordinator._merged_config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}
        mock_coordinator.async_request_refresh = AsyncMock()

        # Setup mock runtime data
        mock_runtime_data = MagicMock(spec=RuntimeData)
        mock_runtime_data.coordinator = mock_coordinator
        mock_runtime_data.config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}

        # Attach runtime data to entry
        mock_config_entry_basic.runtime_data = mock_runtime_data
        mock_config_entry_basic.data = {"enabled": False, "simulation_mode": False, "covers": ["cover.test"]}
        mock_config_entry_basic.options = {}

        # Setup hass mock
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify coordinator refresh was called
        mock_coordinator.async_request_refresh.assert_called_once()

        # Verify full reload was NOT called
        mock_hass_with_spec.config_entries.async_reload.assert_not_called()

        # Verify configs were updated
        assert mock_coordinator._merged_config["enabled"] is False
        assert mock_runtime_data.config["enabled"] is False

    async def test_reload_with_simulating_change_only(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
    ) -> None:
        """Test that changing only 'simulation_mode' triggers coordinator refresh, not full reload.

        When only the 'simulation_mode' flag changes, the integration should:
        - Update the coordinator's merged config
        - Update runtime_data config
        - Trigger a coordinator refresh
        - NOT trigger a full integration reload
        """
        # Setup mock coordinator with old config
        mock_coordinator = MagicMock()
        mock_coordinator._merged_config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}
        mock_coordinator.async_request_refresh = AsyncMock()

        # Setup mock runtime data
        mock_runtime_data = MagicMock(spec=RuntimeData)
        mock_runtime_data.coordinator = mock_coordinator
        mock_runtime_data.config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}

        # Attach runtime data to entry
        mock_config_entry_basic.runtime_data = mock_runtime_data
        mock_config_entry_basic.data = {"enabled": True, "simulation_mode": True, "covers": ["cover.test"]}
        mock_config_entry_basic.options = {}

        # Setup hass mock
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify coordinator refresh was called
        mock_coordinator.async_request_refresh.assert_called_once()

        # Verify full reload was NOT called
        mock_hass_with_spec.config_entries.async_reload.assert_not_called()

        # Verify configs were updated
        assert mock_coordinator._merged_config["simulation_mode"] is True
        assert mock_runtime_data.config["simulation_mode"] is True

    async def test_reload_with_both_runtime_keys_changed(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
    ) -> None:
        """Test that changing both 'enabled' and 'simulation_mode' triggers coordinator refresh.

        When both runtime-configurable keys change, the integration should still
        only trigger a coordinator refresh, not a full reload.
        """
        # Setup mock coordinator with old config
        mock_coordinator = MagicMock()
        mock_coordinator._merged_config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}
        mock_coordinator.async_request_refresh = AsyncMock()

        # Setup mock runtime data
        mock_runtime_data = MagicMock(spec=RuntimeData)
        mock_runtime_data.coordinator = mock_coordinator
        mock_runtime_data.config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}

        # Attach runtime data to entry
        mock_config_entry_basic.runtime_data = mock_runtime_data
        mock_config_entry_basic.data = {"enabled": False, "simulation_mode": True, "covers": ["cover.test"]}
        mock_config_entry_basic.options = {}

        # Setup hass mock
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify coordinator refresh was called
        mock_coordinator.async_request_refresh.assert_called_once()

        # Verify full reload was NOT called
        mock_hass_with_spec.config_entries.async_reload.assert_not_called()

    async def test_reload_with_structural_change_triggers_full_reload(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
    ) -> None:
        """Test that structural changes trigger a full reload, not just coordinator refresh.

        When non-runtime-configurable keys change (like 'covers'), the integration
        should trigger a full reload to properly apply the changes.
        """
        # Setup mock coordinator with old config
        mock_coordinator = MagicMock()
        mock_coordinator._merged_config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test1"]}
        mock_coordinator.async_request_refresh = AsyncMock()

        # Setup mock runtime data
        mock_runtime_data = MagicMock(spec=RuntimeData)
        mock_runtime_data.coordinator = mock_coordinator

        # Attach runtime data to entry
        mock_config_entry_basic.runtime_data = mock_runtime_data
        mock_config_entry_basic.data = {"enabled": True, "simulation_mode": False, "covers": ["cover.test1", "cover.test2"]}
        mock_config_entry_basic.options = {}

        # Setup hass mock
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify full reload WAS called
        mock_hass_with_spec.config_entries.async_reload.assert_called_once_with(mock_config_entry_basic.entry_id)

        # Verify coordinator refresh was NOT called
        mock_coordinator.async_request_refresh.assert_not_called()

    async def test_reload_with_mixed_changes_triggers_full_reload(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
    ) -> None:
        """Test that mixed changes (runtime + structural) trigger a full reload.

        When both runtime-configurable and structural keys change, the integration
        should trigger a full reload to properly handle the structural changes.
        """
        # Setup mock coordinator with old config
        mock_coordinator = MagicMock()
        mock_coordinator._merged_config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test1"]}
        mock_coordinator.async_request_refresh = AsyncMock()

        # Setup mock runtime data
        mock_runtime_data = MagicMock(spec=RuntimeData)
        mock_runtime_data.coordinator = mock_coordinator

        # Attach runtime data to entry
        mock_config_entry_basic.runtime_data = mock_runtime_data
        mock_config_entry_basic.data = {"enabled": False, "simulation_mode": False, "covers": ["cover.test1", "cover.test2"]}
        mock_config_entry_basic.options = {}

        # Setup hass mock
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify full reload WAS called
        mock_hass_with_spec.config_entries.async_reload.assert_called_once_with(mock_config_entry_basic.entry_id)

        # Verify coordinator refresh was NOT called
        mock_coordinator.async_request_refresh.assert_not_called()

    async def test_reload_with_no_changes_triggers_full_reload(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
    ) -> None:
        """Test that reload with no changes still triggers a full reload.

        When the configuration hasn't changed but reload is called anyway,
        the integration should still trigger a full reload as a safety measure.
        """
        # Setup mock coordinator with same config
        mock_coordinator = MagicMock()
        mock_coordinator._merged_config = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}
        mock_coordinator.async_request_refresh = AsyncMock()

        # Setup mock runtime data
        mock_runtime_data = MagicMock(spec=RuntimeData)
        mock_runtime_data.coordinator = mock_coordinator

        # Attach runtime data to entry
        mock_config_entry_basic.runtime_data = mock_runtime_data
        mock_config_entry_basic.data = {"enabled": True, "simulation_mode": False, "covers": ["cover.test"]}
        mock_config_entry_basic.options = {}

        # Setup hass mock
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify full reload WAS called (safety measure when no changes detected)
        mock_hass_with_spec.config_entries.async_reload.assert_called_once_with(mock_config_entry_basic.entry_id)

        # Verify coordinator refresh was NOT called
        mock_coordinator.async_request_refresh.assert_not_called()

    async def test_reload_without_runtime_data_triggers_full_reload(
        self,
        mock_hass_with_spec,
        mock_config_entry_basic,
    ) -> None:
        """Test that reload without runtime_data triggers a full reload.

        If the entry doesn't have runtime_data (edge case), the integration
        should trigger a full reload to ensure proper initialization.
        """
        # Don't set runtime_data on the entry
        mock_config_entry_basic.runtime_data = None
        mock_config_entry_basic.data = {"enabled": False, "simulation_mode": False, "covers": ["cover.test"]}
        mock_config_entry_basic.options = {}

        # Setup hass mock
        mock_hass_with_spec.config_entries = MagicMock()
        mock_hass_with_spec.config_entries.async_reload = AsyncMock()

        # Execute reload
        await async_reload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Verify full reload WAS called
        mock_hass_with_spec.config_entries.async_reload.assert_called_once_with(mock_config_entry_basic.entry_id)
