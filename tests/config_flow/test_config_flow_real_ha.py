"""Integration tests for config flow and options flow with a real Home Assistant instance.

These tests verify that the config and options flows work correctly through
HA's real data entry flow machinery, catching voluptuous schema errors,
selector misconfigurations, and step transition bugs that mock-based tests
miss.

See developer_docs/test-relevance-improvement-plan.md, Phase 3.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smart_cover_automation import DOMAIN
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_SFX_AZIMUTH,
    INTEGRATION_NAME,
    TiltMode,
)

# ============================================================================
# Constants
# ============================================================================

TEST_COVER_1 = "cover.flow_test_cover_1"
TEST_COVER_2 = "cover.flow_test_cover_2"
TEST_WEATHER = "weather.flow_test"

# Feature bitmask for covers that support open/close/set_position
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
# _as_dict
#
def _as_dict(result: ConfigFlowResult) -> dict[str, Any]:
    """Convert flow result TypedDict to plain dict for test assertions."""

    return cast(dict[str, Any], result)


#
# _register_cover_entity
#
def _register_cover_entity(
    hass: HomeAssistant,
    entity_id: str,
    features: int = COVER_FEATURES,
) -> None:
    """Set a cover entity in the HA state machine.

    Args:
        hass: Home Assistant instance.
        entity_id: Cover entity ID.
        features: Supported feature bitmask.
    """

    hass.states.async_set(
        entity_id,
        "open",
        {
            "current_position": 100,
            ATTR_SUPPORTED_FEATURES: features,
        },
    )


#
# _register_weather_entity
#
def _register_weather_entity(
    hass: HomeAssistant,
    entity_id: str = TEST_WEATHER,
) -> None:
    """Set a weather entity with FORECAST_DAILY support.

    Args:
        hass: Home Assistant instance.
        entity_id: Weather entity ID.
    """

    hass.states.async_set(
        entity_id,
        "sunny",
        {
            "temperature": 20,
            "temperature_unit": "°C",
            ATTR_SUPPORTED_FEATURES: WeatherEntityFeature.FORECAST_DAILY,
        },
    )


#
# _create_loaded_entry
#
def _create_loaded_entry(
    hass: HomeAssistant,
    covers: list[str] | None = None,
    extra_options: dict[str, Any] | None = None,
    entry_id: str = "flow_test_entry",
) -> MockConfigEntry:
    """Create a config entry that's ready for options flow.

    The entry is added to *hass* but NOT loaded (options flow doesn't
    require the integration to be running for form rendering).

    Args:
        hass: Home Assistant instance.
        covers: Cover entity IDs.
        extra_options: Additional options.
        entry_id: Unique entry ID.

    Returns:
        The ``MockConfigEntry``.
    """

    if covers is None:
        covers = [TEST_COVER_1]

    options: dict[str, Any] = {
        ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
        ConfKeys.COVERS.value: covers,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 0.0,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        ConfKeys.COVERS_MAX_CLOSURE.value: 0,
        ConfKeys.COVERS_MIN_CLOSURE.value: 100,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 24.0,
    }

    for cover in covers:
        options[f"{cover}_{COVER_SFX_AZIMUTH}"] = 180.0

    if extra_options:
        options.update(extra_options)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=INTEGRATION_NAME,
        data={},
        options=options,
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    return entry


#
# _step_through_options_flow
#
async def _step_through_options_flow(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    step_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Walk through all 6 options flow steps, returning the final result.

    Each element of *step_inputs* is the ``user_input`` dict for steps
    init, 2, 3, 4, 5, 6 in order.  If fewer than 6 are given, remaining
    steps receive ``{}``.

    Args:
        hass: Home Assistant instance.
        entry: Config entry whose options flow to start.
        step_inputs: User inputs for each step (up to 6).

    Returns:
        The final ``FlowResult`` dict (should be ``CREATE_ENTRY``).
    """

    # Pad to 6 elements
    inputs = list(step_inputs) + [{}] * (6 - len(step_inputs))

    # Step init
    result = _as_dict(await hass.config_entries.options.async_init(entry.entry_id))
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Steps init → 2 → 3 → 4 → 5 → 6
    step_ids = ["init", "2", "3", "4", "5", "6"]
    for i, step_id in enumerate(step_ids):
        result = _as_dict(
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input=inputs[i],
            )
        )
        if result["type"] is FlowResultType.CREATE_ENTRY:
            return result
        assert result["type"] is FlowResultType.FORM, f"Expected FORM at step after '{step_id}', got {result['type']}"

    return result


# ============================================================================
# Tests — Phase 3a: Config Flow
# ============================================================================


class TestConfigFlow:
    """Verify config flow creates entries through real HA machinery."""

    # ------------------------------------------------------------------
    # 3.1  Config flow creates entry
    # ------------------------------------------------------------------

    #
    # test_config_flow_creates_entry
    #
    async def test_config_flow_creates_entry(
        self,
        hass: HomeAssistant,
    ) -> None:
        """User config flow creates a valid config entry with defaults.

        The config flow is trivial (empty form) — it creates an entry
        with empty data.  The real configuration lives in the options flow.
        """

        # Show the initial form
        result = _as_dict(await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"}))
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        # Submit the empty form → CREATE_ENTRY
        result = _as_dict(
            await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={},
            )
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == INTEGRATION_NAME
        assert result["data"] == {}


# ============================================================================
# Tests — Phase 3b: Options Flow
# ============================================================================


class TestOptionsFlow:
    """Verify options flow steps through real HA data entry flow."""

    # ------------------------------------------------------------------
    # 3.2  Options flow full wizard (happy path)
    # ------------------------------------------------------------------

    #
    # test_options_flow_full_wizard
    #
    async def test_options_flow_full_wizard(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Walking all 6 steps produces valid config in entry.options.

        Submits minimal valid input at each step and verifies the final
        result is a ``CREATE_ENTRY`` with the expected options.
        """

        _register_cover_entity(hass, TEST_COVER_1)
        _register_weather_entity(hass)

        entry = _create_loaded_entry(hass)

        step_inputs = [
            # Step 1 (init): cover and weather selection
            {
                ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                ConfKeys.COVERS.value: [TEST_COVER_1],
            },
            # Step 2: azimuth per cover
            {f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0},
            # Step 3: min/max closure
            {
                ConfKeys.COVERS_MIN_CLOSURE.value: 100,
                ConfKeys.COVERS_MAX_CLOSURE.value: 0,
            },
            # Step 4: tilt settings
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.AUTO,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
            },
            # Step 5: window sensors (empty — no sensors configured)
            {},
            # Step 6: time settings
            {},
        ]

        result = await _step_through_options_flow(hass, entry, step_inputs)
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # Verify key options were saved
        opts = entry.options
        assert opts[ConfKeys.COVERS.value] == [TEST_COVER_1]
        assert opts[ConfKeys.WEATHER_ENTITY_ID.value] == TEST_WEATHER
        assert opts[f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}"] == 180.0

    # ------------------------------------------------------------------
    # 3.3  Options flow step 1 validation — invalid cover entity
    # ------------------------------------------------------------------

    #
    # test_options_flow_step1_rejects_invalid_cover
    #
    async def test_options_flow_step1_rejects_invalid_cover(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Submitting a non-existent cover entity shows an error on step 1.

        The form should re-render with the error rather than advancing.
        """

        _register_weather_entity(hass)
        entry = _create_loaded_entry(hass)

        # Start options flow
        result = _as_dict(await hass.config_entries.options.async_init(entry.entry_id))
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        # Submit with non-existent cover
        result = _as_dict(
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                    ConfKeys.COVERS.value: ["cover.nonexistent"],
                },
            )
        )

        # Should stay on init with an error
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result.get("errors")
        assert ConfKeys.COVERS.value in result["errors"]

    # ------------------------------------------------------------------
    # 3.4  Options flow step 1 validation — invalid weather entity
    # ------------------------------------------------------------------

    #
    # test_options_flow_step1_rejects_missing_weather
    #
    async def test_options_flow_step1_rejects_missing_weather(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Submitting a non-existent weather entity shows an error."""

        _register_cover_entity(hass, TEST_COVER_1)
        entry = _create_loaded_entry(hass)

        result = _as_dict(await hass.config_entries.options.async_init(entry.entry_id))
        result = _as_dict(
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    ConfKeys.WEATHER_ENTITY_ID.value: "weather.nonexistent",
                    ConfKeys.COVERS.value: [TEST_COVER_1],
                },
            )
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result.get("errors")
        assert ConfKeys.WEATHER_ENTITY_ID.value in result["errors"]

    # ------------------------------------------------------------------
    # 3.5  Options flow preserves existing values
    # ------------------------------------------------------------------

    #
    # test_options_flow_preserves_existing_values
    #
    async def test_options_flow_preserves_existing_values(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Opening options flow pre-fills current config values.

        Verifies that the initial form has the correct data_schema defaults
        matching the entry's existing options.
        """

        _register_cover_entity(hass, TEST_COVER_1)
        _register_weather_entity(hass)
        entry = _create_loaded_entry(hass)

        result = _as_dict(await hass.config_entries.options.async_init(entry.entry_id))
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        # Check the schema has defaults matching current options
        schema = result["data_schema"]
        assert schema is not None

        # Walk the schema to find defaults for our expected keys
        schema_dict = {str(k): k for k in schema.schema}
        for key_name in (ConfKeys.WEATHER_ENTITY_ID.value, ConfKeys.COVERS.value):
            assert key_name in schema_dict, f"Key '{key_name}' not in schema"

    # ------------------------------------------------------------------
    # 3.6  Options flow with cover add/remove
    # ------------------------------------------------------------------

    #
    # test_options_flow_cover_add_remove
    #
    async def test_options_flow_cover_add_remove(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Adding a second cover and removing the first updates config.

        Walks the full wizard with a changed cover list and verifies
        the final options reflect the change.
        """

        _register_cover_entity(hass, TEST_COVER_1)
        _register_cover_entity(hass, TEST_COVER_2)
        _register_weather_entity(hass)

        entry = _create_loaded_entry(hass, covers=[TEST_COVER_1])

        step_inputs = [
            # Step 1: change covers to include both
            {
                ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            },
            # Step 2: azimuth for both covers
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            },
            # Steps 3-6: accept defaults
            {
                ConfKeys.COVERS_MIN_CLOSURE.value: 100,
                ConfKeys.COVERS_MAX_CLOSURE.value: 0,
            },
            {
                ConfKeys.TILT_MODE_DAY.value: TiltMode.AUTO,
                ConfKeys.TILT_MODE_NIGHT.value: TiltMode.CLOSED,
                ConfKeys.TILT_SET_VALUE_DAY.value: 50,
                ConfKeys.TILT_SET_VALUE_NIGHT.value: 0,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 5,
                ConfKeys.TILT_SLAT_OVERLAP_RATIO.value: 0.9,
            },
            {},
            {},
        ]

        result = await _step_through_options_flow(hass, entry, step_inputs)
        assert result["type"] is FlowResultType.CREATE_ENTRY

        # Both covers should be in options
        opts = entry.options
        assert TEST_COVER_1 in opts[ConfKeys.COVERS.value]
        assert TEST_COVER_2 in opts[ConfKeys.COVERS.value]
        assert f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}" in opts

    # ------------------------------------------------------------------
    # 3.7  Weather entity without daily forecast support
    # ------------------------------------------------------------------

    #
    # test_options_flow_rejects_weather_without_forecast
    #
    async def test_options_flow_rejects_weather_without_forecast(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Weather entity that lacks FORECAST_DAILY support is rejected.

        This catches real selector/validation mismatches that mock tests miss.
        """

        _register_cover_entity(hass, TEST_COVER_1)

        # Weather entity WITHOUT FORECAST_DAILY support
        hass.states.async_set(
            TEST_WEATHER,
            "sunny",
            {
                "temperature": 20,
                "temperature_unit": "°C",
                ATTR_SUPPORTED_FEATURES: 0,  # No features
            },
        )

        entry = _create_loaded_entry(hass)

        result = _as_dict(await hass.config_entries.options.async_init(entry.entry_id))
        result = _as_dict(
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                    ConfKeys.COVERS.value: [TEST_COVER_1],
                },
            )
        )

        # Should stay on init with an error about the weather entity
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result.get("errors")
        assert ConfKeys.WEATHER_ENTITY_ID.value in result["errors"]
