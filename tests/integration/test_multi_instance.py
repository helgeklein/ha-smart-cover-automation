"""Integration tests for multi-instance coexistence and service routing.

These tests verify that two config entries can coexist and that services
(``set_lock``, ``logbook_entry``) route to the correct instance.

See developer_docs/test-relevance-improvement-plan.md, Phase 5.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_cover_automation import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    DATA_COORDINATORS,
    DOMAIN,
    SERVICE_FIELD_LOCK_MODE,
    SERVICE_LOGBOOK_ENTRY,
    SERVICE_SET_LOCK,
    LockMode,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

# ============================================================================
# Constants
# ============================================================================

# Instance A
COVER_A = "cover.multi_test_cover_a"
WEATHER_A = "weather.multi_test_a"
ENTRY_ID_A = "multi_test_entry_a"

# Instance B
COVER_B = "cover.multi_test_cover_b"
WEATHER_B = "weather.multi_test_b"
ENTRY_ID_B = "multi_test_entry_b"

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
# _create_entry
#
def _create_entry(
    hass: HomeAssistant,
    cover: str,
    weather: str,
    entry_id: str,
    extra_options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Create and register a config entry.

    Args:
        hass: Home Assistant instance.
        cover: Cover entity ID.
        weather: Weather entity ID.
        entry_id: Unique entry ID.
        extra_options: Additional options.

    Returns:
        The ``MockConfigEntry`` added to *hass*.
    """

    options: dict[str, Any] = {
        ConfKeys.WEATHER_ENTITY_ID.value: weather,
        ConfKeys.COVERS.value: [cover],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 10.0,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        ConfKeys.COVERS_MAX_CLOSURE.value: 0,
        ConfKeys.COVERS_MIN_CLOSURE.value: 100,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        ConfKeys.TEMP_THRESHOLD.value: 24.0,
        f"{cover}_{COVER_SFX_AZIMUTH}": 180.0,
    }
    if extra_options:
        options.update(extra_options)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Multi Test {entry_id}",
        data={},
        options=options,
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    return entry


#
# _register_entities
#
def _register_entities(hass: HomeAssistant) -> None:
    """Register all weather, sun, and cover entities for both instances.

    Args:
        hass: Home Assistant instance.
    """

    for weather_id in (WEATHER_A, WEATHER_B):
        hass.states.async_set(
            weather_id,
            "sunny",
            {"temperature": 20, "temperature_unit": "°C"},
        )

    hass.states.async_set(
        "sun.sun",
        "above_horizon",
        {"elevation": 45.0, "azimuth": 180.0},
    )

    for cover_id in (COVER_A, COVER_B):
        hass.states.async_set(
            cover_id,
            "open",
            {
                "current_position": COVER_POS_FULLY_OPEN,
                ATTR_SUPPORTED_FEATURES: COVER_FEATURES,
            },
        )


#
# _setup_two_instances
#
async def _setup_two_instances(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MockConfigEntry]:
    """Create and load two independent integration instances.

    Args:
        hass: Home Assistant instance.

    Returns:
        Tuple of (entry_a, entry_b).
    """

    _register_entities(hass)

    # Register mock cover service
    if not hass.services.has_service("cover", "set_cover_position"):

        async def _noop(call) -> None:  # noqa: ARG001
            """No-op handler."""

        hass.services.async_register("cover", "set_cover_position", _noop)

    entry_a = _create_entry(hass, COVER_A, WEATHER_A, ENTRY_ID_A)
    entry_b = _create_entry(hass, COVER_B, WEATHER_B, ENTRY_ID_B)

    with patch(
        "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface._get_forecast_max_temp",
        new_callable=AsyncMock,
        return_value=30.0,
    ):
        # Load the first entry via async_setup_component
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Load the second entry directly (component already set up)
        await async_setup_entry(hass, cast(IntegrationConfigEntry, entry_b))
        await hass.async_block_till_done()

    assert entry_a.state is ConfigEntryState.LOADED
    assert entry_b.state is ConfigEntryState.LOADED

    return entry_a, entry_b


# ============================================================================
# Tests — Phase 5: Multi-Instance & Service Routing
# ============================================================================


class TestMultiInstance:
    """Verify multi-instance coexistence and service routing."""

    # ------------------------------------------------------------------
    # 5.1  Two instances load successfully
    # ------------------------------------------------------------------

    #
    # test_two_instances_load
    #
    async def test_two_instances_load(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Two config entries with different covers both reach LOADED state.

        Both coordinators should appear in ``DATA_COORDINATORS``.
        """

        entry_a, entry_b = await _setup_two_instances(hass)

        coordinators = hass.data[DOMAIN][DATA_COORDINATORS]
        assert ENTRY_ID_A in coordinators, "Entry A coordinator missing"
        assert ENTRY_ID_B in coordinators, "Entry B coordinator missing"
        assert coordinators[ENTRY_ID_A] is not coordinators[ENTRY_ID_B]

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_b))
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_a))

    # ------------------------------------------------------------------
    # 5.2  set_lock routes to all instances (global broadcast)
    # ------------------------------------------------------------------

    #
    # test_set_lock_global_broadcast
    #
    async def test_set_lock_global_broadcast(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Calling set_lock without a target updates ALL coordinators."""

        entry_a, entry_b = await _setup_two_instances(hass)

        coordinators = hass.data[DOMAIN][DATA_COORDINATORS]
        coord_a = coordinators[ENTRY_ID_A]
        coord_b = coordinators[ENTRY_ID_B]

        # Both should start UNLOCKED
        assert coord_a.lock_mode == LockMode.UNLOCKED
        assert coord_b.lock_mode == LockMode.UNLOCKED

        # Call set_lock without target → broadcast to all
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LOCK,
            {SERVICE_FIELD_LOCK_MODE: LockMode.FORCE_CLOSE},
            blocking=True,
        )

        # Both should be updated
        assert coord_a.lock_mode == LockMode.FORCE_CLOSE
        assert coord_b.lock_mode == LockMode.FORCE_CLOSE

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_b))
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_a))

    # ------------------------------------------------------------------
    # 5.3  Unloading one instance keeps the other running
    # ------------------------------------------------------------------

    #
    # test_unload_one_instance_keeps_other
    #
    async def test_unload_one_instance_keeps_other(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Unloading entry A does not affect entry B's coordinator."""

        entry_a, entry_b = await _setup_two_instances(hass)

        # Unload entry A
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_a))
        await hass.async_block_till_done()

        # Entry B should still be available
        coordinators = hass.data[DOMAIN][DATA_COORDINATORS]
        assert ENTRY_ID_A not in coordinators, "Entry A should be removed"
        assert ENTRY_ID_B in coordinators, "Entry B should still be present"

        # Services should still be registered (not last entry)
        assert hass.services.has_service(DOMAIN, SERVICE_SET_LOCK)

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_b))

    # ------------------------------------------------------------------
    # 5.4  Services cleaned up on last unload
    # ------------------------------------------------------------------

    #
    # test_logbook_service_removed_on_last_unload
    #
    async def test_logbook_service_removed_on_last_unload(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Logbook service is removed when the last instance unloads."""

        entry_a, entry_b = await _setup_two_instances(hass)

        # Service should exist while entries are loaded
        assert hass.services.has_service(DOMAIN, SERVICE_LOGBOOK_ENTRY)

        # Unload first entry — service should persist
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_a))
        await hass.async_block_till_done()
        assert hass.services.has_service(DOMAIN, SERVICE_LOGBOOK_ENTRY)

        # Unload last entry — logbook service should be removed
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_b))
        await hass.async_block_till_done()
        assert not hass.services.has_service(DOMAIN, SERVICE_LOGBOOK_ENTRY)

    # ------------------------------------------------------------------
    # 5.5  Per-instance lock mode isolation
    # ------------------------------------------------------------------

    #
    # test_per_instance_lock_mode_isolation
    #
    async def test_per_instance_lock_mode_isolation(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Changing lock mode on one coordinator does not affect the other.

        Uses ``coordinator.async_set_lock_mode()`` directly to verify
        instance isolation.
        """

        entry_a, entry_b = await _setup_two_instances(hass)

        coordinators = hass.data[DOMAIN][DATA_COORDINATORS]
        coord_a = coordinators[ENTRY_ID_A]
        coord_b = coordinators[ENTRY_ID_B]

        # Change only coordinator A
        await coord_a.async_set_lock_mode(LockMode.HOLD_POSITION)

        assert coord_a.lock_mode == LockMode.HOLD_POSITION
        assert coord_b.lock_mode == LockMode.UNLOCKED, "Coordinator B should remain UNLOCKED"

        # Cleanup
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_b))
        await async_unload_entry(hass, cast(IntegrationConfigEntry, entry_a))
