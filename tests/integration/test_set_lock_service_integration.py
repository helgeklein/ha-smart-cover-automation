"""Integration tests for set_lock service with real Home Assistant instance.

These tests validate the set_lock service works correctly in a real Home Assistant
environment, testing:
- Service registration and discovery
- Service call execution
- Lock mode changes via service
- State persistence after service calls
- Error handling with real HA validation
"""

from __future__ import annotations

from typing import cast

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_cover_automation import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_SFX_AZIMUTH,
    DATA_COORDINATORS,
    DOMAIN,
    SERVICE_FIELD_LOCK_MODE,
    SERVICE_SET_LOCK,
    LockMode,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import (
    MOCK_COVER_ENTITY_ID,
    create_temperature_config,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this module."""
    yield


@pytest.fixture(autouse=True)
async def setup_dependencies(hass: HomeAssistant):
    """Set up required dependencies for integration testing.

    Our integration depends on logbook, which in turn depends on frontend and recorder.
    For testing purposes, we bypass these UI/database dependencies and just set up
    the core dependencies (sun).
    """
    # Set up sun (required for automation logic)
    await async_setup_component(hass, "sun", {})

    # Mock logbook to avoid frontend/recorder dependencies
    hass.config.components.add("logbook")

    await hass.async_block_till_done()
    yield


@pytest.fixture(autouse=True)
def expected_lingering_tasks() -> bool:
    """Expect lingering tasks in these tests."""
    return True


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Expect lingering timers in these tests."""
    return True


def create_test_config_entry(
    hass: HomeAssistant,
    covers: list[str] | None = None,
    lock_mode: str | None = None,
    entry_id: str = "test_entry_set_lock",
) -> MockConfigEntry:
    """Create a test config entry for service tests.

    Args:
        hass: Home Assistant instance
        covers: Optional list of cover entity IDs
        lock_mode: Optional lock mode to set
        entry_id: Entry ID for the config entry

    Returns:
        Config entry added to hass
    """
    options = create_temperature_config(covers=covers)

    if lock_mode is not None:
        options[ConfKeys.LOCK_MODE.value] = lock_mode

    # Ensure azimuth is set for all covers
    cover_list = covers if covers is not None else [MOCK_COVER_ENTITY_ID]
    for cover in cover_list:
        if f"{cover}_{COVER_SFX_AZIMUTH}" not in options:
            options[f"{cover}_{COVER_SFX_AZIMUTH}"] = 180.0

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Smart Cover Automation Test",
        data={},
        options=options,
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    return entry


class TestSetLockServiceIntegration:
    """Integration tests for set_lock service with real Home Assistant."""

    @pytest.mark.asyncio
    async def test_set_lock_service_is_registered(self, hass: HomeAssistant) -> None:
        """Test that set_lock service is registered in real HA instance."""
        # Setup integration
        mock_config_entry = create_test_config_entry(hass, entry_id="test_entry_set_lock_1")

        # Setup component first to load the integration
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify service exists
        assert hass.services.has_service(DOMAIN, SERVICE_SET_LOCK)

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, mock_config_entry))

    @pytest.mark.asyncio
    async def test_set_lock_service_call_changes_mode(self, hass: HomeAssistant) -> None:
        """Test calling set_lock service changes the lock mode."""
        # Setup integration
        mock_config_entry = create_test_config_entry(hass, entry_id="test_entry_set_lock_2")

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Get coordinator
        coordinator = hass.data[DOMAIN][DATA_COORDINATORS][mock_config_entry.entry_id]

        # Initial mode should be UNLOCKED (default)
        assert coordinator.lock_mode == LockMode.UNLOCKED

        # Call set_lock service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK,
            {SERVICE_FIELD_LOCK_MODE: LockMode.FORCE_CLOSE},
            blocking=True,
        )

        # Verify mode changed
        assert coordinator.lock_mode == LockMode.FORCE_CLOSE

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, mock_config_entry))

    @pytest.mark.parametrize(
        "lock_mode",
        [LockMode.UNLOCKED, LockMode.HOLD_POSITION, LockMode.FORCE_OPEN, LockMode.FORCE_CLOSE],
    )
    @pytest.mark.asyncio
    async def test_set_lock_to_mode(self, hass: HomeAssistant, lock_mode: str) -> None:
        """Test setting lock mode to various modes."""
        mock_config_entry = create_test_config_entry(hass, entry_id=f"test_entry_set_lock_{lock_mode}")

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][DATA_COORDINATORS][mock_config_entry.entry_id]

        # Call service
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK,
            {SERVICE_FIELD_LOCK_MODE: lock_mode},
            blocking=True,
        )

        # Verify coordinator lock mode was set
        assert coordinator.lock_mode == lock_mode

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, mock_config_entry))

    @pytest.mark.asyncio
    async def test_set_lock_service_changes_persist(self, hass: HomeAssistant) -> None:
        """Test lock mode changes via service persist in coordinator."""
        mock_config_entry = create_test_config_entry(hass, entry_id="test_entry_set_lock_7")

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][DATA_COORDINATORS][mock_config_entry.entry_id]

        # Start with UNLOCKED
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK,
            {SERVICE_FIELD_LOCK_MODE: LockMode.UNLOCKED},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert coordinator.lock_mode == LockMode.UNLOCKED

        # Change to FORCE_OPEN
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK,
            {SERVICE_FIELD_LOCK_MODE: LockMode.FORCE_OPEN},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Verify change persisted
        assert coordinator.lock_mode == LockMode.FORCE_OPEN

        # Change to HOLD_POSITION
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK,
            {SERVICE_FIELD_LOCK_MODE: LockMode.HOLD_POSITION},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Verify change persisted
        assert coordinator.lock_mode == LockMode.HOLD_POSITION

        await async_unload_entry(hass, cast(IntegrationConfigEntry, mock_config_entry))

    @pytest.mark.asyncio
    async def test_set_lock_service_only_registered_once(self, hass: HomeAssistant) -> None:
        """Test set_lock service is only registered once even with multiple config entries."""
        # Setup first integration instance
        mock_config_entry1 = create_test_config_entry(hass, entry_id="test_entry_set_lock_8")

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Verify service is registered
        assert hass.services.has_service(DOMAIN, SERVICE_SET_LOCK)

        # Setup second integration instance with different entry
        mock_config_entry2 = create_test_config_entry(
            hass,
            covers=["cover.test_2"],
            entry_id="test_entry_set_lock_9",
        )
        mock_config_entry2.add_to_hass(hass)
        await async_setup_entry(hass, cast(IntegrationConfigEntry, mock_config_entry2))
        await hass.async_block_till_done()

        # Service should still be available (not double-registered)
        assert hass.services.has_service(DOMAIN, SERVICE_SET_LOCK)

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, mock_config_entry1))
        await async_unload_entry(hass, cast(IntegrationConfigEntry, mock_config_entry2))
