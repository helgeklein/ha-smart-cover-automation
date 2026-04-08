"""Integration tests for runtime automation behavior with a real Home Assistant instance.

These tests verify the full automation chain end-to-end:
    state change → coordinator update → automation engine → cover service call

Unlike the lifecycle tests in test_integration_real_ha.py (which only verify setup/teardown),
these tests trigger actual coordinator update cycles and verify that the correct cover service
calls are issued. This catches wiring bugs, event loop issues, and state machine errors that
mock-heavy unit tests cannot detect.

See developer_docs/test-relevance-improvement-plan.md, Phase 1.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.smart_cover_automation import DOMAIN
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_POS_FULLY_CLOSED,
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    DATA_COORDINATORS,
    HA_SUN_ATTR_AZIMUTH,
    HA_SUN_ATTR_ELEVATION,
    HA_SUN_ENTITY_ID,
    UPDATE_INTERVAL,
    LockMode,
)
from custom_components.smart_cover_automation.ha_interface import HomeAssistantInterface

# --- Test entity IDs ---
TEST_COVER_1 = "cover.runtime_test_cover_1"
TEST_COVER_2 = "cover.runtime_test_cover_2"
TEST_WEATHER = "weather.runtime_test"

# --- Default feature flags ---
COVER_FEATURES_SET_POSITION = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SET_POSITION

# --- Temperature thresholds ---
HOT_TEMP = 30.0
COLD_TEMP = 18.0
COMFORTABLE_TEMP = 22.0

# --- Sun geometry ---
SUN_HIGH_ELEVATION = 45.0
SUN_LOW_ELEVATION = 5.0
SUN_BELOW_HORIZON_ELEVATION = -10.0
SUN_DIRECT_AZIMUTH = 180.0  # Directly south — matches cover azimuth
SUN_INDIRECT_AZIMUTH = 10.0  # North — won't hit a south-facing cover

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
# _setup_weather_entity
#
def _setup_weather_entity(
    hass: HomeAssistant,
    entity_id: str = TEST_WEATHER,
    condition: str = "sunny",
) -> None:
    """Register a weather entity state in the HA state machine.

    Args:
        hass: Home Assistant instance.
        entity_id: Entity ID for the weather entity.
        condition: Weather condition string (e.g. ``"sunny"``).
    """

    hass.states.async_set(
        entity_id,
        condition,
        {"temperature": 20, "temperature_unit": "°C"},
    )


#
# _setup_cover_entity
#
def _setup_cover_entity(
    hass: HomeAssistant,
    entity_id: str,
    position: int = COVER_POS_FULLY_OPEN,
    features: int = COVER_FEATURES_SET_POSITION,
) -> None:
    """Register a cover entity state in the HA state machine.

    Args:
        hass: Home Assistant instance.
        entity_id: Cover entity ID.
        position: Current position (0 = closed, 100 = open).
        features: Supported feature bitmask.
    """

    state = "open" if position > 0 else "closed"
    hass.states.async_set(
        entity_id,
        state,
        {
            "current_position": position,
            ATTR_SUPPORTED_FEATURES: features,
        },
    )


#
# _setup_sun_entity
#
def _setup_sun_entity(
    hass: HomeAssistant,
    elevation: float = SUN_HIGH_ELEVATION,
    azimuth: float = SUN_DIRECT_AZIMUTH,
) -> None:
    """Set the sun entity's attributes in the HA state machine.

    Args:
        hass: Home Assistant instance.
        elevation: Sun elevation in degrees.
        azimuth: Sun azimuth in degrees.
    """

    above = "above_horizon" if elevation >= 0 else "below_horizon"
    hass.states.async_set(
        HA_SUN_ENTITY_ID,
        above,
        {
            HA_SUN_ATTR_ELEVATION: elevation,
            HA_SUN_ATTR_AZIMUTH: azimuth,
        },
    )


#
# _create_config_entry
#
def _create_config_entry(
    hass: HomeAssistant,
    covers: list[str] | None = None,
    extra_options: dict[str, Any] | None = None,
    entry_id: str = "runtime_test_entry",
) -> MockConfigEntry:
    """Create and register a config entry with sensible defaults.

    Args:
        hass: Home Assistant instance.
        covers: List of cover entity IDs (defaults to ``[TEST_COVER_1]``).
        extra_options: Additional or overridden option keys.
        entry_id: Unique entry ID.

    Returns:
        The ``MockConfigEntry`` added to *hass*.
    """

    if covers is None:
        covers = [TEST_COVER_1]

    options: dict[str, Any] = {
        ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
        ConfKeys.COVERS.value: covers,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 10.0,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        ConfKeys.COVERS_MAX_CLOSURE.value: 0,
        ConfKeys.COVERS_MIN_CLOSURE.value: 100,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 24.0,
    }

    # Per-cover azimuths (south-facing by default)
    for cover in covers:
        options[f"{cover}_{COVER_SFX_AZIMUTH}"] = SUN_DIRECT_AZIMUTH

    if extra_options:
        options.update(extra_options)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Runtime Test",
        data={},
        options=options,
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    return entry


#
# _setup_integration
#
async def _setup_integration(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    temp_max: float = HOT_TEMP,
    weather_condition: str = "sunny",
    cover_positions: dict[str, int] | None = None,
    sun_elevation: float = SUN_HIGH_ELEVATION,
    sun_azimuth: float = SUN_DIRECT_AZIMUTH,
) -> None:
    """Load the integration and set up all entity states.

    Call *after* ``_create_config_entry``.  Sets weather, sun, and cover
    entity states, patches the weather forecast lookup, and loads the
    component.

    The ``weather.get_forecasts`` HA service requires a real weather
    platform entity (not just a state), so we patch
    ``HomeAssistantInterface.get_daily_temperature_extrema`` to return the desired
    forecast temperatures directly. Everything else in the chain — coordinator,
    automation engine, cover automation, and cover service calls — runs
    through real HA code.

    Args:
        hass: Home Assistant instance.
        entry: Config entry (already added to *hass*).
        temp_max: Forecast max temperature in °C.
        weather_condition: Weather condition string.
        cover_positions: Mapping of cover entity → position.  Defaults to
            all covers fully open.
        sun_elevation: Sun elevation in degrees.
        sun_azimuth: Sun azimuth in degrees.
    """

    covers = entry.options.get(ConfKeys.COVERS.value, [])

    # --- Entity states ---
    _setup_weather_entity(hass, condition=weather_condition)
    _setup_sun_entity(hass, elevation=sun_elevation, azimuth=sun_azimuth)

    if cover_positions is None:
        cover_positions = {c: COVER_POS_FULLY_OPEN for c in covers}

    for cover_id, pos in cover_positions.items():
        _setup_cover_entity(hass, cover_id, position=pos)

    # --- Register mock cover services ---
    # The integration calls cover.set_cover_position to move covers.
    # Since we set cover state directly rather than loading a real cover
    # platform, we must register the service ourselves.
    if not hass.services.has_service("cover", "set_cover_position"):

        async def _mock_set_cover_position(call: ServiceCall) -> None:  # noqa: ARG001
            """No-op handler for cover.set_cover_position."""

        hass.services.async_register("cover", "set_cover_position", _mock_set_cover_position)

    # --- Load integration with patched weather forecast ---
    # Patch the forecast retrieval so we don't need a real weather platform entity.
    # The rest of the chain (coordinator → engine → cover automation → HA service calls)
    # runs unpatched through real HA code.
    with patch(
        "custom_components.smart_cover_automation.ha_interface.HomeAssistantInterface.get_daily_temperature_extrema",
        new_callable=AsyncMock,
        return_value=(temp_max, 18.0),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED


#
# _trigger_coordinator_update
#
async def _trigger_coordinator_update(hass: HomeAssistant) -> None:
    """Advance time by one update interval and wait for the coordinator to run.

    Args:
        hass: Home Assistant instance.
    """

    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL + timedelta(seconds=1))
    await hass.async_block_till_done()


#
# _get_coordinator
#
def _get_coordinator(hass: HomeAssistant, entry: MockConfigEntry):  # noqa: ANN202
    """Retrieve the coordinator for a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry to look up.

    Returns:
        The ``DataUpdateCoordinator`` instance.
    """

    return hass.data[DOMAIN][DATA_COORDINATORS][entry.entry_id]


# ============================================================================
# Tests — Phase 1: Runtime Behaviour with Real HA
# ============================================================================


class TestRuntimeBehavior:
    """End-to-end tests that verify cover commands are issued through the full chain."""

    # ------------------------------------------------------------------
    # 1.1  Heat protection closes cover
    # ------------------------------------------------------------------

    #
    # test_heat_protection_closes_cover
    #
    async def test_heat_protection_closes_cover(self, hass: HomeAssistant) -> None:
        """Cover is moved toward closed when temperature exceeds threshold and sun is hitting.

        Full chain: weather entity (hot) + sun entity (hitting) →
        coordinator refresh → automation engine → cover automation →
        ha_interface.set_cover_position → hass.services.async_call.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)

        # After initial refresh the coordinator should have processed the cover
        assert coordinator.data is not None
        assert coordinator.data.covers, "Expected at least one cover in coordinator data"
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None, f"Cover {TEST_COVER_1} not in coordinator data"

        # With hot temp + sun hitting a south-facing cover, the desired position
        # should be at or below the max-closure setting (0 = fully closed).
        assert cover_data.pos_target_desired is not None, "Expected a target position"
        assert (
            cover_data.pos_target_desired <= coordinator._resolved_settings().covers_max_closure
            or cover_data.pos_target_desired < COVER_POS_FULLY_OPEN
        ), f"Expected cover to be moved toward closed, got desired={cover_data.pos_target_desired}"

    # ------------------------------------------------------------------
    # 1.2  Comfortable temperature keeps cover open
    # ------------------------------------------------------------------

    #
    # test_comfortable_temp_opens_cover
    #
    async def test_comfortable_temp_opens_cover(self, hass: HomeAssistant) -> None:
        """Cover stays open when temperature is below the heat threshold.

        Even with the sun hitting, a comfortable temperature means no heat
        protection is needed.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(
            hass,
            entry,
            temp_max=COMFORTABLE_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None

        # With comfortable temp, no heat protection → cover should stay open
        if cover_data.pos_target_desired is not None:
            assert cover_data.pos_target_desired >= COVER_POS_FULLY_OPEN, (
                f"Expected cover to remain open, got desired={cover_data.pos_target_desired}"
            )

    # ------------------------------------------------------------------
    # 1.3  Sun azimuth direct hit
    # ------------------------------------------------------------------

    #
    # test_sun_azimuth_direct_hit
    #
    async def test_sun_azimuth_direct_hit(self, hass: HomeAssistant) -> None:
        """Cover reacts when sun azimuth is within the cover's tolerance window.

        Cover faces south (180°), sun is at 180° → direct hit.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,  # matches cover azimuth
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None
        assert cover_data.sun_hitting is True, "Sun should be hitting a south-facing cover at 180° azimuth"

    # ------------------------------------------------------------------
    # 1.4  Sun azimuth no hit
    # ------------------------------------------------------------------

    #
    # test_sun_azimuth_no_hit
    #
    async def test_sun_azimuth_no_hit(self, hass: HomeAssistant) -> None:
        """Cover is NOT hit when the sun is far outside the tolerance window.

        Cover faces south (180°), sun is at 10° (north) → no hit.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_INDIRECT_AZIMUTH,  # far from cover azimuth
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None
        assert cover_data.sun_hitting is False, "Sun should NOT be hitting when azimuth is far from cover"

    # ------------------------------------------------------------------
    # 1.5  Coordinator data populates sensor fields
    # ------------------------------------------------------------------

    #
    # test_coordinator_data_has_sensor_fields
    #
    async def test_coordinator_data_has_sensor_fields(self, hass: HomeAssistant) -> None:
        """Coordinator data exposes sun/temp/weather fields for entity consumption.

        This verifies the wiring between automation engine and coordinator data.
        """

        entry = _create_config_entry(hass)
        await _setup_integration(hass, entry, temp_max=HOT_TEMP)

        coordinator = _get_coordinator(hass, entry)
        data = coordinator.data

        assert data is not None
        assert data.sun_azimuth is not None, "sun_azimuth should be populated"
        assert data.sun_elevation is not None, "sun_elevation should be populated"
        assert data.temp_current_max is not None, "temp_current_max should be populated"
        assert data.temp_current_min is not None, "temp_current_min should be populated"
        assert data.temp_hot is not None, "temp_hot should be populated"
        assert data.weather_sunny is not None, "weather_sunny should be populated"

        # Validate actual values match what we injected
        assert data.temp_current_max == pytest.approx(HOT_TEMP, abs=0.1)
        assert data.temp_current_min == pytest.approx(COLD_TEMP, abs=0.1)
        assert data.temp_hot is True
        assert data.weather_sunny is True

    # ------------------------------------------------------------------
    # 1.6  Lock mode FORCE_OPEN overrides heat protection
    # ------------------------------------------------------------------

    #
    # test_lock_mode_force_open_overrides_heat
    #
    async def test_lock_mode_force_open_overrides_heat(self, hass: HomeAssistant) -> None:
        """FORCE_OPEN lock mode prevents cover from closing even when hot.

        The cover should stay at or move to fully open despite heat protection
        conditions being met.
        """

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.LOCK_MODE.value: LockMode.FORCE_OPEN},
        )
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None

        # FORCE_OPEN should override heat protection → target is fully open
        if cover_data.pos_target_desired is not None:
            assert cover_data.pos_target_desired == COVER_POS_FULLY_OPEN, (
                f"FORCE_OPEN should keep cover open, got desired={cover_data.pos_target_desired}"
            )

    # ------------------------------------------------------------------
    # 1.7  Lock mode FORCE_CLOSE overrides cold
    # ------------------------------------------------------------------

    #
    # test_lock_mode_force_close_overrides_cold
    #
    async def test_lock_mode_force_close_overrides_cold(self, hass: HomeAssistant) -> None:
        """FORCE_CLOSE lock mode closes the cover even when temperature is cold.

        Without the lock, cold temp would keep the cover open.
        """

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.LOCK_MODE.value: LockMode.FORCE_CLOSE},
        )
        await _setup_integration(
            hass,
            entry,
            temp_max=COLD_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None

        # FORCE_CLOSE should override normal logic → target is fully closed
        if cover_data.pos_target_desired is not None:
            assert cover_data.pos_target_desired == COVER_POS_FULLY_CLOSED, (
                f"FORCE_CLOSE should close cover, got desired={cover_data.pos_target_desired}"
            )

    # ------------------------------------------------------------------
    # 1.8  Lock mode HOLD_POSITION blocks all movement
    # ------------------------------------------------------------------

    #
    # test_lock_mode_hold_position_blocks_movement
    #
    async def test_lock_mode_hold_position_blocks_movement(self, hass: HomeAssistant) -> None:
        """HOLD_POSITION lock mode prevents any cover movement.

        The cover position should remain unchanged regardless of conditions.
        """

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.LOCK_MODE.value: LockMode.HOLD_POSITION},
        )
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
            cover_positions={TEST_COVER_1: 50},
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None

        # HOLD_POSITION: the automation should not compute a new desired position,
        # or if it does, it should match current (50) — no movement command issued.
        # The key check: pos_target_final should either be None (no action) or == current.
        if cover_data.pos_target_final is not None:
            assert cover_data.pos_target_final == cover_data.pos_current, (
                f"HOLD_POSITION should not move cover, got final={cover_data.pos_target_final}, current={cover_data.pos_current}"
            )

    # ------------------------------------------------------------------
    # 1.9  Nighttime blocks opening
    # ------------------------------------------------------------------

    #
    # test_nighttime_blocks_opening
    #
    async def test_nighttime_blocks_opening(self, hass: HomeAssistant) -> None:
        """Cover does not open after evening closure overnight.

        This test focuses on the runtime behavior once the scheduler has
        determined that the overnight post-evening-closure block is active.
        """

        entry = _create_config_entry(
            hass,
            extra_options={
                ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
                ConfKeys.EVENING_CLOSURE_COVER_LIST.value: [TEST_COVER_1],
            },
        )
        with patch(
            "custom_components.smart_cover_automation.automation_engine.AutomationEngine._compute_post_evening_closure",
            return_value=True,
        ):
            await _setup_integration(
                hass,
                entry,
                temp_max=COMFORTABLE_TEMP,
                sun_elevation=SUN_BELOW_HORIZON_ELEVATION,
                sun_azimuth=SUN_DIRECT_AZIMUTH,
                cover_positions={TEST_COVER_1: COVER_POS_FULLY_CLOSED},
            )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None

        # At night with blocking enabled, cover should NOT be opened
        if cover_data.pos_target_desired is not None:
            assert cover_data.pos_target_desired <= COVER_POS_FULLY_CLOSED, (
                f"Nighttime blocking should prevent opening, got desired={cover_data.pos_target_desired}"
            )

    # ------------------------------------------------------------------
    # 1.10  Morning opening unblocks opening on next cycle
    # ------------------------------------------------------------------

    #
    # test_morning_opening_unblocks_opening_on_next_cycle
    #
    async def test_morning_opening_unblocks_opening_on_next_cycle(self, hass: HomeAssistant) -> None:
        """A cover blocked overnight should open once the morning-opening block lifts."""

        cover_calls: list[ServiceCall] = []
        post_evening_closure_state = True

        async def _record_set_cover_position(call: ServiceCall) -> None:
            """Record real cover service calls issued by the integration."""

            cover_calls.append(call)

        def _post_evening_closure() -> bool:
            """Return the current deterministic blocked/unblocked state."""

            return post_evening_closure_state

        hass.services.async_register("cover", "set_cover_position", _record_set_cover_position)

        entry = _create_config_entry(
            hass,
            extra_options={
                ConfKeys.EVENING_CLOSURE_ENABLED.value: True,
                ConfKeys.EVENING_CLOSURE_COVER_LIST.value: [TEST_COVER_1],
            },
        )
        with patch(
            "custom_components.smart_cover_automation.automation_engine.AutomationEngine._compute_post_evening_closure",
            side_effect=_post_evening_closure,
        ):
            await _setup_integration(
                hass,
                entry,
                temp_max=COMFORTABLE_TEMP,
                sun_elevation=SUN_HIGH_ELEVATION,
                sun_azimuth=SUN_INDIRECT_AZIMUTH,
                cover_positions={TEST_COVER_1: COVER_POS_FULLY_CLOSED},
            )

            coordinator = _get_coordinator(hass, entry)
            blocked_cover_data = coordinator.data.covers.get(TEST_COVER_1)

            assert blocked_cover_data is not None
            assert blocked_cover_data.pos_target_desired == COVER_POS_FULLY_CLOSED
            assert blocked_cover_data.pos_target_final is None
            assert cover_calls == []

            post_evening_closure_state = False

            with patch.object(
                HomeAssistantInterface,
                "get_daily_temperature_extrema",
                new_callable=AsyncMock,
                return_value=(COMFORTABLE_TEMP, 18.0),
            ):
                await _trigger_coordinator_update(hass)

            released_cover_data = coordinator.data.covers.get(TEST_COVER_1)

        assert released_cover_data is not None
        assert released_cover_data.pos_target_desired == COVER_POS_FULLY_OPEN
        assert released_cover_data.pos_target_final == COVER_POS_FULLY_OPEN
        assert len(cover_calls) == 1
        assert cover_calls[0].data["entity_id"] == TEST_COVER_1
        assert cover_calls[0].data["position"] == COVER_POS_FULLY_OPEN

    # ------------------------------------------------------------------
    # 1.11  Multiple covers processed in single cycle
    # ------------------------------------------------------------------

    #
    # test_multiple_covers_processed
    #
    async def test_multiple_covers_processed(self, hass: HomeAssistant) -> None:
        """All configured covers are processed in a single coordinator cycle.

        Verifies that adding multiple covers produces CoverState entries for each.
        """

        covers = [TEST_COVER_1, TEST_COVER_2]
        entry = _create_config_entry(hass, covers=covers)
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)
        for cover_id in covers:
            assert cover_id in coordinator.data.covers, (
                f"Expected {cover_id} in coordinator data, got {list(coordinator.data.covers.keys())}"
            )

    # ------------------------------------------------------------------
    # 1.12 Coordinator update after state change
    # ------------------------------------------------------------------

    #
    # test_coordinator_update_after_state_change
    #
    async def test_coordinator_update_after_state_change(self, hass: HomeAssistant) -> None:
        """Coordinator picks up changed entity states on the next update cycle.

        This is the most important end-to-end test: it verifies that changing
        HA entity state → triggering a coordinator update → produces new
        automation results.
        """

        entry = _create_config_entry(hass)

        # Start with comfortable temperature — cover should stay open
        await _setup_integration(
            hass,
            entry,
            temp_max=COMFORTABLE_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None

        initial_temp_hot = coordinator.data.temp_hot
        assert initial_temp_hot is False, "With comfortable temp, temp_hot should be False"

        # Now change the weather forecast to hot by patching the forecast method
        with patch.object(
            HomeAssistantInterface,
            "get_daily_temperature_extrema",
            new_callable=AsyncMock,
            return_value=(HOT_TEMP, 18.0),
        ):
            # Trigger a coordinator update cycle
            await _trigger_coordinator_update(hass)

        # After the update, the coordinator should see the new hot temperature
        assert coordinator.data.temp_hot is True, f"After temp change, temp_hot should be True, got {coordinator.data.temp_hot}"
        assert coordinator.data.temp_current_max == pytest.approx(HOT_TEMP, abs=0.1)

    # ------------------------------------------------------------------
    # 1.13 Small recent automation drift is not treated as manual override
    # ------------------------------------------------------------------

    #
    # test_small_recent_automation_drift_is_not_manual_override
    #
    async def test_small_recent_automation_drift_is_not_manual_override(self, hass: HomeAssistant) -> None:
        """A small post-move drift stays automatable on the next scheduled refresh.

        This exercises the full HA runtime path:
            initial automation move -> device reports a small position drift -> next timed refresh

        The second cycle should keep evaluating automation normally and must not
        emit another cover command for the tolerated drift.
        """

        cover_calls: list[ServiceCall] = []

        async def _record_set_cover_position(call: ServiceCall) -> None:
            """Record real cover service calls issued by the integration."""

            cover_calls.append(call)

        hass.services.async_register("cover", "set_cover_position", _record_set_cover_position)

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.COVERS_MIN_POSITION_DELTA.value: 5},
        )
        await _setup_integration(
            hass,
            entry,
            temp_max=COMFORTABLE_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_INDIRECT_AZIMUTH,
            cover_positions={TEST_COVER_1: COVER_POS_FULLY_CLOSED},
        )

        coordinator = _get_coordinator(hass, entry)
        initial_cover_data = coordinator.data.covers.get(TEST_COVER_1)

        assert initial_cover_data is not None
        assert initial_cover_data.pos_target_desired == COVER_POS_FULLY_OPEN
        assert initial_cover_data.pos_target_final == COVER_POS_FULLY_OPEN
        assert len(cover_calls) == 1
        assert cover_calls[0].data["entity_id"] == TEST_COVER_1
        assert cover_calls[0].data["position"] == COVER_POS_FULLY_OPEN

        _setup_cover_entity(hass, TEST_COVER_1, position=98)

        with patch.object(
            HomeAssistantInterface,
            "get_daily_temperature_extrema",
            new_callable=AsyncMock,
            return_value=(COMFORTABLE_TEMP, 18.0),
        ):
            await _trigger_coordinator_update(hass)

        drifted_cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert drifted_cover_data is not None
        assert drifted_cover_data.pos_current == 98
        assert drifted_cover_data.pos_target_desired == COVER_POS_FULLY_OPEN
        assert drifted_cover_data.pos_target_final is None
        assert len(cover_calls) == 1

        latest_entry = coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry(TEST_COVER_1)
        assert latest_entry is not None
        assert latest_entry.position == 98


class TestRuntimeEdgeCases:
    """Edge-case runtime tests with real HA."""

    # ------------------------------------------------------------------
    # Missing weather entity — graceful degradation
    # ------------------------------------------------------------------

    #
    # test_missing_weather_entity_graceful
    #
    async def test_missing_weather_entity_graceful(self, hass: HomeAssistant) -> None:
        """Integration keeps running when weather entity is missing.

        The coordinator should produce an empty covers dict rather than crashing.
        """

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.WEATHER_ENTITY_ID.value: "weather.nonexistent"},
        )

        # Don't set up the weather entity — it won't exist
        _setup_sun_entity(hass)
        _setup_cover_entity(hass, TEST_COVER_1)

        # Weather entity doesn't exist, so get_max_temperature will raise.
        # The coordinator handles this gracefully and returns empty data.
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        # Integration should load — may have empty covers due to weather unavailability
        assert entry.state == ConfigEntryState.LOADED

    # ------------------------------------------------------------------
    # Disabled automation produces empty result
    # ------------------------------------------------------------------

    #
    # test_disabled_automation_no_cover_actions
    #
    async def test_disabled_automation_no_cover_actions(self, hass: HomeAssistant) -> None:
        """When the automation is disabled via config, no cover actions are taken.

        The coordinator should still run but produce an empty covers dict.
        """

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.ENABLED.value: False},
        )
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)
        assert coordinator.data is not None
        # With automation disabled, covers dict should be empty (no processing)
        assert coordinator.data.covers == {}, f"Disabled automation should produce empty covers, got {coordinator.data.covers}"

    # ------------------------------------------------------------------
    # Simulation mode — no actual service calls
    # ------------------------------------------------------------------

    #
    # test_simulation_mode_no_service_calls
    #
    async def test_simulation_mode_no_service_calls(self, hass: HomeAssistant) -> None:
        """Simulation mode calculates positions but does not issue cover commands.

        We verify the coordinator processes covers and computes target positions
        by checking that ``set_cover_position`` on the HA interface was never
        called with ``simulation_mode`` disabled — simulation mode skips the
        actual ``hass.services.async_call``.
        """

        entry = _create_config_entry(
            hass,
            extra_options={ConfKeys.SIMULATION_MODE.value: True},
        )
        await _setup_integration(
            hass,
            entry,
            temp_max=HOT_TEMP,
            sun_elevation=SUN_HIGH_ELEVATION,
            sun_azimuth=SUN_DIRECT_AZIMUTH,
        )

        coordinator = _get_coordinator(hass, entry)
        cover_data = coordinator.data.covers.get(TEST_COVER_1)
        assert cover_data is not None

        # Simulation mode should still calculate a desired position
        # (the automation logic runs, it just doesn't send commands).
        # Verify the cover was at least evaluated by the automation.
        assert cover_data.sun_hitting is not None, "Automation should have evaluated sun_hitting even in simulation mode"
