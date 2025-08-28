"""Integration tests for Smart Cover Automation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smart_cover_automation.coordinator import (
    ConfigurationError,
    DataUpdateCoordinator,
    EntityUnavailableError,
    InvalidSensorReadingError,
    SensorNotFoundError,
)

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    MockConfigEntry,
    create_sun_config,
    create_temperature_config,
)


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    async def test_temperature_automation_complete_cycle(self) -> None:
        """Test complete temperature automation cycle."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, config_entry)

        # Mock states for full cycle test
        temp_states = ["26.0", "22.0", "18.0"]  # Hot -> Comfortable -> Cold
        cover_positions = [100, 0, 0]  # Open -> Closed -> Closed
        expected_positions = [0, 0, 100]  # Close -> Maintain -> Open

        for i, (temp, current_pos, expected_pos) in enumerate(
            zip(temp_states, cover_positions, expected_positions)
        ):
            # Setup states
            temp_state = MagicMock()
            temp_state.state = temp
            temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

            cover_state = MagicMock()
            cover_state.attributes = {
                "current_position": current_pos,
                "supported_features": 15,
            }

            hass.states.get.side_effect = lambda entity_id: {
                MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
                MOCK_COVER_ENTITY_ID: cover_state,
            }.get(entity_id)

            hass.services.async_call.reset_mock()

            # Execute automation
            try:
                result = await coordinator._async_update_data()

                # Verify result structure
                if not result or "covers" not in result:
                    raise AssertionError(f"Invalid result structure in cycle {i}")

                cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
                if cover_data["desired_position"] != expected_pos:
                    raise AssertionError(
                        f"Cycle {i}: Expected position {expected_pos}, "
                        f"got {cover_data['desired_position']}"
                    )

                # Check service calls only when position changes
                if current_pos != expected_pos:
                    if not hass.services.async_call.called:
                        raise AssertionError(
                            f"Cycle {i}: Service should have been called"
                        )
                else:
                    if hass.services.async_call.called:
                        raise AssertionError(
                            f"Cycle {i}: Service should not have been called"
                        )

            except Exception as e:
                raise AssertionError(f"Automation failed in cycle {i}: {e}") from e

    async def test_sun_automation_daily_cycle(self) -> None:
        """Test sun automation through daily cycle."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_sun_config())
        coordinator = DataUpdateCoordinator(hass, config_entry)

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
            cover_state.attributes = {"current_position": 100, "supported_features": 15}

            hass.states.get.side_effect = lambda entity_id: {
                MOCK_SUN_ENTITY_ID: sun_state,
                MOCK_COVER_ENTITY_ID: cover_state,
            }.get(entity_id)

            result = await coordinator._async_update_data()

            if not result or "covers" not in result:
                raise AssertionError(
                    f"Invalid result for sun position {elevation}°, {azimuth}°"
                )

            cover_data = result["covers"][MOCK_COVER_ENTITY_ID]

            # Verify logical sun behavior
            if elevation < 20:  # Low sun
                if cover_data["desired_position"] != 100:
                    raise AssertionError(f"Low sun should open covers: {elevation}°")
            elif elevation >= 20 and azimuth == 180.0:  # High sun, direct south
                if cover_data["desired_position"] == 100:
                    raise AssertionError(
                        f"Direct sun should close covers: {elevation}°, {azimuth}°"
                    )

    async def test_error_recovery_scenarios(self) -> None:
        """Test error handling and recovery scenarios."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, config_entry)

        # Test 1: Temperature sensor temporarily unavailable
        hass.states.get.return_value = None

        with pytest.raises(SensorNotFoundError):
            await coordinator._async_update_data()

        # Test 2: Invalid temperature reading with recovery
        temp_state = MagicMock()
        temp_state.state = "invalid"
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

        hass.states.get.return_value = temp_state

        with pytest.raises(InvalidSensorReadingError):
            await coordinator._async_update_data()

        # Test 3: Service call failure handling
        temp_state.state = "26.0"  # Valid hot temperature
        cover_state = MagicMock()
        cover_state.attributes = {"current_position": 100, "supported_features": 15}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
            MOCK_COVER_ENTITY_ID: cover_state,
        }.get(entity_id)

        # Make service call fail but automation should continue
        hass.services.async_call.side_effect = OSError("Service failed")

        # Should not raise exception, just log error
        result = await coordinator._async_update_data()
        if not result or "covers" not in result:
            raise AssertionError("Automation should continue despite service failure")

    async def test_configuration_validation(self) -> None:
        """Test configuration validation scenarios."""
        hass = MagicMock()

        # Test empty covers list
        config = create_temperature_config()
        config["covers"] = []
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, config_entry)

        with pytest.raises(ConfigurationError):
            await coordinator._async_update_data()

        # Test invalid automation type
        config = create_temperature_config()
        config["automation_type"] = "invalid"
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, config_entry)

        with pytest.raises(ConfigurationError):
            await coordinator._async_update_data()

    async def test_concurrent_cover_control(self) -> None:
        """Test controlling multiple covers simultaneously."""
        hass = MagicMock()
        config = create_temperature_config()
        config["covers"] = ["cover.living_room", "cover.bedroom", "cover.kitchen"]
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, config_entry)

        # Setup hot temperature scenario
        temp_state = MagicMock()
        temp_state.state = "26.0"
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

        result = await coordinator._async_update_data()

        # Verify all covers were processed
        if len(result["covers"]) != 3:
            raise AssertionError(f"Expected 3 covers, got {len(result['covers'])}")

        # Verify all covers should close (position 0) due to hot temperature
        for cover_id in config["covers"]:
            if result["covers"][cover_id]["desired_position"] != 0:
                raise AssertionError(f"Cover {cover_id} should close in hot weather")

        # Verify service calls were made for covers that needed to move
        call_count = hass.services.async_call.call_count
        if call_count == 0:
            raise AssertionError("No service calls made for cover control")

    async def test_mixed_cover_capabilities(self) -> None:
        """Test handling covers with different capabilities."""
        hass = MagicMock()
        config = create_temperature_config()
        config["covers"] = ["cover.smart", "cover.basic"]
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, config_entry)

        # Setup cold temperature to open covers
        temp_state = MagicMock()
        temp_state.state = "18.0"
        temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

        # Smart cover with position support
        smart_cover = MagicMock()
        smart_cover.attributes = {"current_position": 0, "supported_features": 15}

        # Basic cover with only open/close
        basic_cover = MagicMock()
        basic_cover.attributes = {"current_position": 0, "supported_features": 3}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
            "cover.smart": smart_cover,
            "cover.basic": basic_cover,
        }.get(entity_id)

        await coordinator._async_update_data()

        # Check that appropriate services were called
        calls = [call.args for call in hass.services.async_call.call_args_list]

        # Should have calls for both covers
        if len(calls) < 2:
            raise AssertionError(f"Expected at least 2 service calls, got {len(calls)}")

        # Smart cover should use set_cover_position
        smart_call = next(
            (call for call in calls if call[2]["entity_id"] == "cover.smart"), None
        )
        if not smart_call or smart_call[1] != "set_cover_position":
            raise AssertionError("Smart cover should use set_cover_position")

        # Basic cover should use open_cover
        basic_call = next(
            (call for call in calls if call[2]["entity_id"] == "cover.basic"), None
        )
        if not basic_call or basic_call[1] != "open_cover":
            raise AssertionError("Basic cover should use open_cover")
