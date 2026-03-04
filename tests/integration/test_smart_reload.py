"""Integration tests for the smart reload mechanism with a real Home Assistant instance.

These tests verify that the update listener correctly distinguishes between
runtime-configurable key changes (coordinator refresh only) and structural
key changes (full entry reload).

See developer_docs/test-relevance-improvement-plan.md, Phase 4.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_cover_automation import DOMAIN
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    DATA_COORDINATORS,
    LockMode,
)

# ============================================================================
# Constants
# ============================================================================

TEST_COVER_1 = "cover.reload_test_cover_1"
TEST_COVER_2 = "cover.reload_test_cover_2"
TEST_WEATHER = "weather.reload_test"
ENTRY_ID = "reload_test_entry"

# Feature bitmask for covers
COVER_FEATURES = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SET_POSITION

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this module."""

    yield


@pytest.fixture(autouse=True)
async def setup_dependencies(hass: HomeAssistant):
    """Set up required dependencies (sun component, logbook mock)."""

    await async_setup_component(hass, "sun", {})
    hass.config.components.add("logbook")
    await hass.async_block_till_done()
    yield


@pytest.fixture(autouse=True)
def expected_lingering_tasks() -> bool:
    """Coordinator timers may linger after test teardown — that's expected."""

    return True


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Coordinator timers may linger after test teardown — that's expected."""

    return True


# ============================================================================
# Helpers
# ============================================================================


#
# _setup_entities
#
def _setup_entities(
    hass: HomeAssistant,
    covers: list[str] | None = None,
) -> None:
    """Register weather, sun, and cover entities in the HA state machine.

    Args:
        hass: Home Assistant instance.
        covers: Cover entity IDs to register.
    """

    if covers is None:
        covers = [TEST_COVER_1]

    hass.states.async_set(
        TEST_WEATHER,
        "sunny",
        {"temperature": 20, "temperature_unit": "°C"},
    )
    hass.states.async_set(
        "sun.sun",
        "above_horizon",
        {"elevation": 45.0, "azimuth": 180.0},
    )
    for cover_id in covers:
        hass.states.async_set(
            cover_id,
            "open",
            {
                "current_position": COVER_POS_FULLY_OPEN,
                ATTR_SUPPORTED_FEATURES: COVER_FEATURES,
            },
        )


#
# _create_and_load_entry
#
async def _create_and_load_entry(
    hass: HomeAssistant,
    covers: list[str] | None = None,
    extra_options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Create a config entry, set up entities, and load the integration.

    Args:
        hass: Home Assistant instance.
        covers: Cover entity IDs.
        extra_options: Additional option overrides.

    Returns:
        The loaded ``MockConfigEntry``.
    """

    if covers is None:
        covers = [TEST_COVER_1]

    _setup_entities(hass, covers)

    options: dict[str, Any] = {
        ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
        ConfKeys.COVERS.value: covers,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 10.0,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        ConfKeys.COVERS_MAX_CLOSURE.value: 0,
        ConfKeys.COVERS_MIN_CLOSURE.value: 100,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        ConfKeys.BLOCK_OPENING_AFTER_EVENING_CLOSURE.value: True,
        ConfKeys.TEMP_THRESHOLD.value: 24.0,
    }
    for cover in covers:
        options[f"{cover}_{COVER_SFX_AZIMUTH}"] = 180.0

    if extra_options:
        options.update(extra_options)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Reload Test",
        data={},
        options=options,
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)

    # Register mock cover service
    if not hass.services.has_service("cover", "set_cover_position"):

        async def _noop(call) -> None:  # noqa: ARG001
            """No-op handler."""

        hass.services.async_register("cover", "set_cover_position", _noop)

    # Patch forecast and load
    with patch(
        "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface._get_forecast_max_temp",
        new_callable=AsyncMock,
        return_value=30.0,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


#
# _get_coordinator
#
def _get_coordinator(hass: HomeAssistant, entry: MockConfigEntry):  # noqa: ANN202
    """Retrieve the coordinator for a config entry."""

    return hass.data[DOMAIN][DATA_COORDINATORS][entry.entry_id]


# ============================================================================
# Tests — Phase 4: Smart Reload End-to-End
# ============================================================================


class TestSmartReload:
    """Verify the smart reload mechanism with a real HA instance."""

    # ------------------------------------------------------------------
    # 4.1  Runtime key change → coordinator refresh, no full reload
    # ------------------------------------------------------------------

    #
    # test_runtime_key_change_refreshes_only
    #
    async def test_runtime_key_change_refreshes_only(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Changing a runtime-configurable key refreshes the coordinator
        without a full reload cycle.

        ``temp_threshold`` is ``runtime_configurable=True``, so changing it
        should update the coordinator's config and trigger a refresh while
        the entry remains ``LOADED`` throughout.
        """

        entry = await _create_and_load_entry(hass)
        coordinator = _get_coordinator(hass, entry)

        # Capture the coordinator object ID to verify it's the same instance
        original_coordinator_id = id(coordinator)

        # Change a runtime-configurable key
        new_options = {**entry.options, ConfKeys.TEMP_THRESHOLD.value: 30.0}

        with patch(
            "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface._get_forecast_max_temp",
            new_callable=AsyncMock,
            return_value=30.0,
        ):
            hass.config_entries.async_update_entry(entry, options=new_options)
            await hass.async_block_till_done()

        # Entry should remain LOADED (no reload cycle)
        assert entry.state is ConfigEntryState.LOADED

        # Should be the SAME coordinator instance (no teardown/recreate)
        current_coordinator = _get_coordinator(hass, entry)
        assert id(current_coordinator) == original_coordinator_id

        # Coordinator config should have the new threshold
        assert current_coordinator._merged_config.get(ConfKeys.TEMP_THRESHOLD.value) == 30.0

    # ------------------------------------------------------------------
    # 4.2  Structural key change → full entry reload
    # ------------------------------------------------------------------

    #
    # test_structural_key_change_reloads_entry
    #
    async def test_structural_key_change_reloads_entry(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Changing a structural key triggers a full entry reload.

        ``nighttime_block_opening`` is NOT runtime-configurable, so
        changing it should cause a full unload → setup cycle.
        """

        _setup_entities(hass, [TEST_COVER_1])  # Ensure entities exist for reload

        entry = await _create_and_load_entry(hass)
        coordinator = _get_coordinator(hass, entry)
        original_coordinator_id = id(coordinator)

        # Change a structural key
        new_options = {**entry.options, ConfKeys.BLOCK_OPENING_AFTER_EVENING_CLOSURE.value: False}

        with patch(
            "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface._get_forecast_max_temp",
            new_callable=AsyncMock,
            return_value=30.0,
        ):
            hass.config_entries.async_update_entry(entry, options=new_options)
            await hass.async_block_till_done()

        # Entry should still be LOADED after the reload completes
        assert entry.state is ConfigEntryState.LOADED

        # Should be a DIFFERENT coordinator instance (full reload)
        new_coordinator = _get_coordinator(hass, entry)
        assert id(new_coordinator) != original_coordinator_id

    # ------------------------------------------------------------------
    # 4.3  Multiple runtime keys in one update → coordinator refresh
    # ------------------------------------------------------------------

    #
    # test_multiple_runtime_keys_single_refresh
    #
    async def test_multiple_runtime_keys_single_refresh(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Changing several runtime-configurable keys at once triggers
        a single coordinator refresh without a full reload.
        """

        entry = await _create_and_load_entry(hass)
        coordinator = _get_coordinator(hass, entry)
        original_coordinator_id = id(coordinator)

        # Change multiple runtime-configurable keys at once
        new_options = {
            **entry.options,
            ConfKeys.TEMP_THRESHOLD.value: 28.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 15.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 60.0,
        }

        with patch(
            "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface._get_forecast_max_temp",
            new_callable=AsyncMock,
            return_value=30.0,
        ):
            hass.config_entries.async_update_entry(entry, options=new_options)
            await hass.async_block_till_done()

        # Same coordinator (no reload)
        assert entry.state is ConfigEntryState.LOADED
        current_coordinator = _get_coordinator(hass, entry)
        assert id(current_coordinator) == original_coordinator_id

        # All values updated
        cfg = current_coordinator._merged_config
        assert cfg.get(ConfKeys.TEMP_THRESHOLD.value) == 28.0
        assert cfg.get(ConfKeys.SUN_ELEVATION_THRESHOLD.value) == 15.0
        assert cfg.get(ConfKeys.SUN_AZIMUTH_TOLERANCE.value) == 60.0

    # ------------------------------------------------------------------
    # 4.4  Lock mode change via options update → coordinator refresh
    # ------------------------------------------------------------------

    #
    # test_lock_mode_change_via_options_update
    #
    async def test_lock_mode_change_via_options_update(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Changing lock_mode through options update triggers refresh.

        ``lock_mode`` is runtime-configurable, so it should update via
        coordinator refresh without a full reload.
        """

        entry = await _create_and_load_entry(hass)
        coordinator = _get_coordinator(hass, entry)
        original_coordinator_id = id(coordinator)

        # Default is UNLOCKED — change to FORCE_OPEN
        new_options = {**entry.options, ConfKeys.LOCK_MODE.value: LockMode.FORCE_OPEN}

        with patch(
            "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface._get_forecast_max_temp",
            new_callable=AsyncMock,
            return_value=30.0,
        ):
            hass.config_entries.async_update_entry(entry, options=new_options)
            await hass.async_block_till_done()

        # Same coordinator instance
        assert entry.state is ConfigEntryState.LOADED
        current_coordinator = _get_coordinator(hass, entry)
        assert id(current_coordinator) == original_coordinator_id

        # Lock mode updated
        assert current_coordinator.lock_mode == LockMode.FORCE_OPEN
