"""Integration tests for Smart Cover Automation."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.coordinator import (
    ConfigurationError,
    DataUpdateCoordinator,
    InvalidSensorReadingError,
    SensorNotFoundError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    MockConfigEntry,
    create_sun_config,
    create_temperature_config,
)

# Constants for magic numbers
HOT_TEMP = "26.0"
COMFORTABLE_TEMP = "22.0"
COLD_TEMP = "18.0"
COVER_OPEN = 100
COVER_CLOSED = 0
LOW_SUN_ELEVATION = 20.0
DIRECT_SUN_AZIMUTH = 180.0
NUM_COVERS = 3
MIN_SERVICE_CALLS = 2


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    async def test_temperature_automation_complete_cycle(self) -> None:
        """Test complete temperature automation cycle."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock states for full cycle test
        temp_states = [HOT_TEMP, COMFORTABLE_TEMP, COLD_TEMP]
        cover_positions = [COVER_OPEN, COVER_CLOSED, COVER_CLOSED]
        expected_positions = [COVER_CLOSED, COVER_CLOSED, COVER_OPEN]

        for i, (temp, current_pos, expected_pos) in enumerate(zip(temp_states, cover_positions, expected_positions, strict=False)):
            # Setup states
            temp_state = MagicMock()
            temp_state.state = temp
            temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

            cover_state = MagicMock()
            cover_state.attributes = {
                "current_position": current_pos,
                "supported_features": 15,
            }

            hass.states.get.side_effect = lambda entity_id, ts=temp_state, cs=cover_state: {
                MOCK_TEMP_SENSOR_ENTITY_ID: ts,
                MOCK_COVER_ENTITY_ID: cs,
            }.get(entity_id)

            hass.services.async_call.reset_mock()

            # Execute automation
            try:
                await coordinator.async_refresh()
                result = coordinator.data

                # Verify result structure
                assert result is not None, f"Result is None in cycle {i}"
                assert "covers" in result, f"Invalid result structure in cycle {i}"

                cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
                assert cover_data["desired_position"] == expected_pos, (
                    f"Cycle {i}: Expected position {expected_pos}, got {cover_data['desired_position']}"
                )

                # Check service calls only when position changes
                if current_pos != expected_pos:
                    assert hass.services.async_call.called, f"Cycle {i}: Service should have been called"
                else:
                    assert not hass.services.async_call.called, f"Cycle {i}: Service should not have been called"

            except Exception as e:
                pytest.fail(f"Automation failed in cycle {i}: {e}")

    async def test_sun_automation_daily_cycle(self) -> None:
        """Test sun automation through daily cycle."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_sun_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Simulate sun positions throughout day
        sun_positions = [
            (10.0, 90.0),  # Low sun, east
            (45.0, 135.0),  # High sun, southeast
            (50.0, 180.0),  # High sun, south (direct)
            (30.0, 225.0),  # Lower sun, southwest
            (5.0, 270.0),  # Low sun, west
        ]

        for elevation, azimuth in sun_positions:
            sun_state = MagicMock()
            sun_state.attributes = {"elevation": elevation, "azimuth": azimuth}

            cover_state = MagicMock()
            cover_state.attributes = {
                "current_position": COVER_OPEN,
                "supported_features": 15,
            }

            hass.states.get.side_effect = lambda entity_id, ss=sun_state, cs=cover_state: {
                MOCK_SUN_ENTITY_ID: ss,
                MOCK_COVER_ENTITY_ID: cs,
            }.get(entity_id)

            await coordinator.async_refresh()
            result = coordinator.data

            assert result is not None, "Result is None"
            assert "covers" in result, f"Invalid result for sun position {elevation}°, {azimuth}°"

            cover_data = result["covers"][MOCK_COVER_ENTITY_ID]

            # Verify logical sun behavior
            if elevation < LOW_SUN_ELEVATION:  # Low sun
                assert cover_data["desired_position"] == COVER_OPEN, f"Low sun should open covers: {elevation}°"
            elif elevation >= LOW_SUN_ELEVATION and azimuth == DIRECT_SUN_AZIMUTH:
                assert cover_data["desired_position"] != COVER_OPEN, f"Direct sun should close covers: {elevation}°, {azimuth}°"

    async def test_error_recovery_scenarios(self) -> None:
        """Test error handling and recovery scenarios."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test 1: Temperature sensor temporarily unavailable
        cover_state = MagicMock()
        cover_state.attributes = {
            "current_position": COVER_OPEN,
            "supported_features": 15,
        }
        # Return None for temp sensor but a valid cover state
        hass.states.get.side_effect = lambda entity_id, cs=cover_state: {
            MOCK_TEMP_SENSOR_ENTITY_ID: None,
            MOCK_COVER_ENTITY_ID: cs,
        }.get(entity_id)

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, SensorNotFoundError)

        # Test 2: Invalid temperature reading with recovery
        temp_state = MagicMock()
        temp_state.state = "invalid"
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
        # Keep cover available but provide invalid temp
        hass.states.get.side_effect = lambda entity_id, ts=temp_state, cs=cover_state: {
            MOCK_TEMP_SENSOR_ENTITY_ID: ts,
            MOCK_COVER_ENTITY_ID: cs,
        }.get(entity_id)

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, InvalidSensorReadingError)

        # Test 3: Service call failure handling
        temp_state.state = HOT_TEMP  # Valid hot temperature
        cover_state = MagicMock()
        cover_state.attributes = {
            "current_position": COVER_OPEN,
            "supported_features": 15,
        }

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
            MOCK_COVER_ENTITY_ID: cover_state,
        }.get(entity_id)

        # Make service call fail but automation should continue
        hass.services.async_call.side_effect = OSError("Service failed")

        # Should not raise exception, just log error
        await coordinator.async_refresh()
        result = coordinator.data
        assert result is not None, "Automation should continue despite service failure"
        assert "covers" in result, "Automation should continue despite service failure"

    async def test_configuration_validation(self) -> None:
        """Test configuration validation scenarios."""
        hass = MagicMock()

        # Test empty covers list
        config = create_temperature_config()
        config["covers"] = []
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)

    # No automation_type concept anymore; invalid type test removed

    async def test_concurrent_cover_control(self) -> None:
        """Test controlling multiple covers simultaneously."""
        hass = MagicMock()
        config = create_temperature_config()
        config["covers"] = ["cover.living_room", "cover.bedroom", "cover.kitchen"]
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup hot temperature scenario
        temp_state = MagicMock()
        temp_state.state = HOT_TEMP
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

        # Create different cover states
        cover_states = {}
        for i, cover_id in enumerate(config["covers"]):
            cover_state = MagicMock()
            cover_state.attributes = {
                "current_position": 100 - (i * 20),  # Different positions
                "supported_features": 15,
            }
            cover_states[cover_id] = cover_state

        def get_state(entity_id: str) -> MagicMock | None:
            if entity_id == MOCK_TEMP_SENSOR_ENTITY_ID:
                return temp_state
            return cover_states.get(entity_id)

        hass.states.get.side_effect = get_state
        hass.services.async_call.reset_mock()

        await coordinator.async_refresh()
        result = coordinator.data

        # Verify all covers were processed
        assert len(result["covers"]) == NUM_COVERS, f"Expected {NUM_COVERS} covers, got {len(result['covers'])}"

        # Verify all covers should close (position 0) due to hot temperature
        for cover_id in config["covers"]:
            assert result["covers"][cover_id]["desired_position"] == COVER_CLOSED, f"Cover {cover_id} should close in hot weather"

        # Verify service calls were made for covers that needed to move
        call_count = hass.services.async_call.call_count
        assert call_count > 0, "No service calls made for cover control"

    async def test_mixed_cover_capabilities(self) -> None:
        """Test handling covers with different capabilities."""
        hass = MagicMock()
        config = create_temperature_config()
        config["covers"] = ["cover.smart", "cover.basic"]
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup cold temperature to open covers
        temp_state = MagicMock()
        temp_state.state = COLD_TEMP
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

        # Smart cover with position support
        smart_cover = MagicMock()
        smart_cover.attributes = {
            "current_position": COVER_CLOSED,
            "supported_features": 15,
        }

        # Basic cover with only open/close
        basic_cover = MagicMock()
        basic_cover.attributes = {
            "current_position": COVER_CLOSED,
            "supported_features": 3,
        }

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
            "cover.smart": smart_cover,
            "cover.basic": basic_cover,
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
