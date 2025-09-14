"""Integration tests for Smart Cover Automation."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION

from custom_components.smart_cover_automation.config import (
    ConfKeys,
)
from custom_components.smart_cover_automation.coordinator import (
    ConfigurationError,
    DataUpdateCoordinator,
    InvalidSensorReadingError,
    TempSensorNotFoundError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    MockConfigEntry,
    create_temperature_config,
)

# Test constants
HOT_TEMP = "26.0"
COMFORTABLE_TEMP = "22.0"
COLD_TEMP = "18.0"
COVER_OPEN = 100
COVER_CLOSED = 0

# Constants for magic numbers
NUM_COVERS = 3
MIN_SERVICE_CALLS = 2


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    async def test_temperature_automation_complete_cycle(self) -> None:
        """Test complete temperature automation cycle with combined AND logic."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        config_entry = MockConfigEntry(create_temperature_config())  # Both automations now always active
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test scenarios with combined logic (temp AND sun)
        test_scenarios = [
            # (temp, sun_elevation, sun_azimuth, current_pos, expected_pos, description)
            (HOT_TEMP, 30.0, 180.0, COVER_OPEN, COVER_CLOSED, "Hot + sun hitting -> close"),
            (COMFORTABLE_TEMP, 30.0, 180.0, COVER_CLOSED, COVER_OPEN, "Comfortable + sun hitting -> open (not hot)"),
            (COLD_TEMP, 10.0, 90.0, COVER_CLOSED, COVER_OPEN, "Cold + sun not hitting -> open"),
            (HOT_TEMP, 10.0, 90.0, COVER_OPEN, COVER_OPEN, "Hot + sun not hitting -> open (not hitting)"),
        ]

        for i, (temp, elevation, azimuth, current_pos, expected_pos, description) in enumerate(test_scenarios):
            # Setup states for combined automation
            temp_state = MagicMock()
            temp_state.state = temp
            temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

            cover_state = MagicMock()
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: current_pos,
                "supported_features": 15,
            }

            sun_state = MagicMock()
            sun_state.state = "above_horizon"
            sun_state.attributes = {"elevation": elevation, "azimuth": azimuth}

            hass.states.get.side_effect = lambda entity_id, ts=temp_state, cs=cover_state, ss=sun_state: {
                MOCK_TEMP_SENSOR_ENTITY_ID: ts,
                MOCK_COVER_ENTITY_ID: cs,
                MOCK_SUN_ENTITY_ID: ss,
            }.get(entity_id)

            hass.services.async_call.reset_mock()

            # Execute automation
            try:
                await coordinator.async_refresh()
                result = coordinator.data

                # Verify result structure
                assert result is not None, f"Result is None in scenario {i}: {description}"
                assert ConfKeys.COVERS.value in result, f"Invalid result structure in scenario {i}: {description}"

                cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
                assert cover_data["sca_cover_desired_position"] == expected_pos, (
                    f"Scenario {i} ({description}): Expected position {expected_pos}, got {cover_data['sca_cover_desired_position']}"
                )

                # Check service calls only when position changes
                if current_pos != expected_pos:
                    assert hass.services.async_call.called, f"Scenario {i} ({description}): Service should have been called"
                else:
                    assert not hass.services.async_call.called, f"Scenario {i} ({description}): Service should not have been called"

            except Exception as e:
                pytest.fail(f"Automation failed in scenario {i} ({description}): {e}")

    async def test_sun_automation_daily_cycle(self) -> None:
        """Test sun automation through daily cycle with combined AND logic."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())  # Both automations now always active
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test scenarios for combined temp+sun logic throughout the day
        test_scenarios = [
            # (elevation, azimuth, temp, expected_pos, description)
            (10.0, 90.0, HOT_TEMP, COVER_OPEN, "Low sun, east + hot -> no change (sun not hitting)"),
            (45.0, 135.0, HOT_TEMP, COVER_CLOSED, "High sun, southeast + hot -> close (sun hitting, temp hot)"),
            (50.0, 180.0, HOT_TEMP, COVER_CLOSED, "High sun, south + hot -> close (both conditions met)"),
            (30.0, 225.0, HOT_TEMP, COVER_CLOSED, "Lower sun, southwest + hot -> close (sun hitting, temp hot)"),
            (5.0, 270.0, HOT_TEMP, COVER_OPEN, "Low sun, west + hot -> no change (sun not hitting)"),
            (50.0, 180.0, COMFORTABLE_TEMP, COVER_OPEN, "High sun, south + comfortable -> no change (temp not hot)"),
            (50.0, 180.0, COLD_TEMP, COVER_OPEN, "High sun, south + cold -> open (cold temp wins)"),
        ]

        for i, (elevation, azimuth, temp, expected_pos, description) in enumerate(test_scenarios):
            sun_state = MagicMock()
            sun_state.state = "above_horizon"
            sun_state.attributes = {"elevation": elevation, "azimuth": azimuth}

            temp_state = MagicMock()
            temp_state.state = temp
            temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

            cover_state = MagicMock()
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: COVER_OPEN,
                "supported_features": 15,
            }

            hass.states.get.side_effect = lambda entity_id, ss=sun_state, ts=temp_state, cs=cover_state: {
                MOCK_SUN_ENTITY_ID: ss,
                MOCK_TEMP_SENSOR_ENTITY_ID: ts,
                MOCK_COVER_ENTITY_ID: cs,
            }.get(entity_id)

            await coordinator.async_refresh()
            result = coordinator.data

            assert result is not None, f"Result is None in scenario {i}: {description}"
            assert ConfKeys.COVERS.value in result, f"Invalid result for scenario {i}: {description}"

            cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
            assert cover_data["sca_cover_desired_position"] == expected_pos, (
                f"Scenario {i} ({description}): Expected {expected_pos}, got {cover_data['desired_position']}"
            )

    async def test_error_recovery_scenarios(self) -> None:
        """Test error handling and recovery scenarios."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test 1: Temperature sensor temporarily unavailable
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: COVER_OPEN,
            "supported_features": 15,
        }
        # Return None for temp sensor but a valid cover state
        hass.states.get.side_effect = lambda entity_id, cs=cover_state: {
            MOCK_TEMP_SENSOR_ENTITY_ID: None,
            MOCK_COVER_ENTITY_ID: cs,
            MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
        }.get(entity_id)

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, TempSensorNotFoundError)

        # Test 2: Invalid temperature reading with recovery
        temp_state = MagicMock()
        temp_state.state = "invalid"
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
        # Keep cover available but provide invalid temp
        hass.states.get.side_effect = lambda entity_id, ts=temp_state, cs=cover_state: {
            MOCK_TEMP_SENSOR_ENTITY_ID: ts,
            MOCK_COVER_ENTITY_ID: cs,
            MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
        }.get(entity_id)

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, InvalidSensorReadingError)

        # Test 3: Service call failure handling
        temp_state.state = HOT_TEMP  # Valid hot temperature
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: COVER_OPEN,
            "supported_features": 15,
        }

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
        }.get(entity_id)

        # Make service call fail but automation should continue
        hass.services.async_call.side_effect = OSError("Service failed")

        # Should not raise exception, just log error
        await coordinator.async_refresh()
        result = coordinator.data
        assert result is not None, "Automation should continue despite service failure"
        assert ConfKeys.COVERS.value in result, "Automation should continue despite service failure"

    async def test_configuration_validation(self) -> None:
        """Test configuration validation scenarios."""
        hass = MagicMock()

        # Test empty covers list
        config = create_temperature_config()
        config[ConfKeys.COVERS.value] = []
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)

    # No automation_type concept anymore; invalid type test removed

    async def test_concurrent_cover_control(self) -> None:
        """Test controlling multiple covers simultaneously."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        covers = ["cover.living_room", "cover.bedroom", "cover.kitchen"]
        config = create_temperature_config(covers=covers)
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup hot temperature scenario
        temp_state = MagicMock()
        temp_state.state = HOT_TEMP
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

        # Create sun state for combined automation
        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": 50.0, "azimuth": 180.0}  # Direct sun hitting

        # Create different cover states
        cover_states = {}
        for i, cover_id in enumerate(covers):
            cover_state = MagicMock()
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: 100 - (i * 20),  # Different positions
                "supported_features": 15,
            }
            cover_states[cover_id] = cover_state

        def get_state(entity_id: str) -> MagicMock | None:
            if entity_id == MOCK_TEMP_SENSOR_ENTITY_ID:
                return temp_state
            if entity_id == MOCK_SUN_ENTITY_ID:
                return sun_state
            return cover_states.get(entity_id)

        hass.states.get.side_effect = get_state
        hass.services.async_call.reset_mock()

        await coordinator.async_refresh()
        result = coordinator.data

        # Verify all covers were processed
        assert len(result[ConfKeys.COVERS.value]) == NUM_COVERS, f"Expected {NUM_COVERS} covers, got {len(result['covers'])}"

        # Verify all covers should close (position 0) due to hot temperature AND sun hitting
        for cover_id in covers:
            assert result[ConfKeys.COVERS.value][cover_id]["sca_cover_desired_position"] == COVER_CLOSED, (
                f"Cover {cover_id} should close in hot weather with sun hitting"
            )

        # Verify service calls were made for covers that needed to move
        call_count = hass.services.async_call.call_count
        assert call_count > 0, "No service calls made for cover control"

    async def test_mixed_cover_capabilities(self) -> None:
        """Test handling covers with different capabilities."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.services.async_call = AsyncMock()
        covers = ["cover.smart", "cover.basic"]
        config = create_temperature_config(covers=covers)
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup cold temperature to open covers
        temp_state = MagicMock()
        temp_state.state = COLD_TEMP
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

        # Smart cover with position support
        smart_cover = MagicMock()
        smart_cover.attributes = {
            ATTR_CURRENT_POSITION: COVER_CLOSED,
            "supported_features": 15,
        }

        # Basic cover with only open/close
        basic_cover = MagicMock()
        basic_cover.attributes = {
            ATTR_CURRENT_POSITION: COVER_CLOSED,
            "supported_features": 3,
        }

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
            "cover.smart": smart_cover,
            "cover.basic": basic_cover,
            MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
        }.get(entity_id)

        await coordinator.async_refresh()

        # Check that appropriate services were called
        calls = [call.args for call in hass.services.async_call.call_args_list]

        # Should have calls for both covers
        assert len(calls) >= MIN_SERVICE_CALLS, f"Expected at least {MIN_SERVICE_CALLS} service calls, got {len(calls)}"

        # Smart cover should use set_cover_position
        smart_call = next((call for call in calls if call[2]["entity_id"] == "cover.smart"), None)
        assert smart_call is not None, "No call found for smart cover"
        assert smart_call[1] == "set_cover_position", "Smart cover should use set_cover_position"

        # Basic cover should use open_cover
        basic_call = next((call for call in calls if call[2]["entity_id"] == "cover.basic"), None)
        assert basic_call is not None, "No call found for basic cover"
        assert basic_call[1] == "open_cover", "Basic cover should use open_cover"
