"""Tests for the Smart Cover Automation coordinator."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.smart_cover_automation.const import (
    CONF_AUTOMATION_TYPE,
    CONF_COVERS,
)
from custom_components.smart_cover_automation.coordinator import (
    ConfigurationError,
    DataUpdateCoordinator,
    EntityUnavailableError,
    InvalidSensorReadingError,
    SensorNotFoundError,
    ServiceCallError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    MockConfigEntry,
    assert_service_called,
    create_sun_config,
    create_temperature_config,
)

# Constants
HOT_TEMP = "26.0"
COLD_TEMP = "18.0"
COMFORTABLE_TEMP = "22.5"
OPEN_POSITION = 100
CLOSED_POSITION = 0
PARTIAL_POSITION = 50
HIGH_ELEVATION = 45.0
LOW_ELEVATION = 15.0
DIRECT_AZIMUTH = 180.0
INDIRECT_AZIMUTH = 90.0
TILT_ANGLE = 20.0
CLOSED_TILT_POSITION = 0


class TestDataUpdateCoordinator:
    """Test DataUpdateCoordinator."""

    @pytest.fixture
    def coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a coordinator instance."""
        config_entry = MockConfigEntry(create_temperature_config())
        return DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

    @pytest.fixture
    def sun_coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a sun coordinator instance."""
        config_entry = MockConfigEntry(create_sun_config())
        return DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

    async def test_init(self, coordinator: DataUpdateCoordinator) -> None:
        """Test coordinator initialization."""
        coor = cast(DataUpdateCoordinator, coordinator)
        assert coor.name == "smart_cover_automation"
        assert coor.config_entry is not None
        # Guard against Optional[timedelta] in typing
        assert coor.update_interval is not None
        assert coor.update_interval.total_seconds() == 60

    async def test_temperature_automation_hot(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test temperature automation when too hot."""
        # Setup - temperature above maximum
        mock_temperature_state.state = HOT_TEMP  # Above 24°C max
        mock_cover_state.attributes["current_position"] = OPEN_POSITION  # Fully open

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify
        assert result is not None
        assert MOCK_COVER_ENTITY_ID in result["covers"]
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["current_temp"] == float(HOT_TEMP)
        assert cover_data["desired_position"] == CLOSED_POSITION  # Should close

        # Verify service call
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=CLOSED_POSITION,
        )

    async def test_temperature_automation_cold(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test temperature automation when too cold."""
        # Setup - temperature below minimum
        mock_temperature_state.state = COLD_TEMP  # Below 21°C min
        mock_cover_state.attributes["current_position"] = (
            CLOSED_POSITION  # Fully closed
        )

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["current_temp"] == float(COLD_TEMP)
        assert cover_data["desired_position"] == OPEN_POSITION  # Should open

        # Verify service call
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=OPEN_POSITION,
        )

    async def test_temperature_automation_comfortable(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test temperature automation when temperature is comfortable."""
        # Setup - temperature in range
        mock_temperature_state.state = COMFORTABLE_TEMP  # Between 21-24°C
        mock_cover_state.attributes["current_position"] = PARTIAL_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["current_temp"] == float(COMFORTABLE_TEMP)
        assert cover_data["desired_position"] == PARTIAL_POSITION  # Should maintain

        # Verify no service call made
        mock_hass.services.async_call.assert_not_called()

    async def test_temperature_sensor_not_found(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when temperature sensor not found."""
        # Ensure cover is available so sensor error is evaluated
        cover_state = MagicMock()
        cover_state.attributes = {
            "current_position": OPEN_POSITION,
            "supported_features": CoverEntityFeature.SET_POSITION,
        }
        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: None,  # Sensor missing
            MOCK_COVER_ENTITY_ID: cover_state,  # Cover available
        }.get(entity_id)
        await coordinator.async_refresh()
        # DataUpdateCoordinator captures exceptions; verify last_exception
        assert isinstance(coordinator.last_exception, SensorNotFoundError)
        assert "sensor.temperature" in str(coordinator.last_exception)

    async def test_temperature_sensor_invalid_reading(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test error when temperature sensor has invalid reading."""
        mock_temperature_state.state = "invalid"
        mock_hass.states.get.return_value = mock_temperature_state
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, InvalidSensorReadingError)
        assert "invalid" in str(coordinator.last_exception)

    async def test_sun_automation_direct_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun automation with direct sunlight."""
        # Setup - sun directly south, high elevation
        mock_sun_state.attributes = {
            "elevation": HIGH_ELEVATION,
            "azimuth": DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes["current_position"] = OPEN_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        await sun_coordinator.async_refresh()
        result = sun_coordinator.data

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["sun_elevation"] == HIGH_ELEVATION
        assert cover_data["sun_azimuth"] == DIRECT_AZIMUTH
        assert (
            cover_data["desired_position"] == CLOSED_TILT_POSITION
        )  # Should close fully by default

    async def test_sun_automation_respects_max_closure_option(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Direct sun should use configured max_closure instead of default."""
        config = create_sun_config()
        config["max_closure"] = 60  # cap direct hit to 60%
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

        mock_sun_state.attributes = {
            "elevation": HIGH_ELEVATION,
            "azimuth": DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes["current_position"] = OPEN_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        # With max_closure=60 and direct hit, desired = 100 - 60 = 40
        assert cover_data["desired_position"] == 40

    async def test_sun_automation_low_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun automation with low sun elevation."""
        # Setup - sun below threshold
        mock_sun_state.attributes = {
            "elevation": LOW_ELEVATION,
            "azimuth": DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes["current_position"] = PARTIAL_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        await sun_coordinator.async_refresh()
        result = sun_coordinator.data

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["desired_position"] == OPEN_POSITION  # Should open fully

    async def test_sun_automation_not_hitting_window_above_threshold(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Sun above threshold but not hitting window should open fully (with logging path)."""
        config = create_sun_config()
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

        # Sun above threshold but azimuth far from south direction (window south)
        mock_sun_state.attributes = {
            "elevation": HIGH_ELEVATION,
            "azimuth": INDIRECT_AZIMUTH,  # 90° vs south 180° => angle 90° > tolerance
        }

        # Cover is partially closed to force potential change to OPEN
        mock_cover_state.attributes["current_position"] = PARTIAL_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["desired_position"] == OPEN_POSITION
        # angle_difference should be computed when elevation >= threshold
        assert cover_data["angle_difference"] is not None

    async def test_sun_automation_no_sun_entity(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when sun entity not found."""
        # Ensure cover is available so sun entity error is evaluated
        cover_state = MagicMock()
        cover_state.attributes = {
            "current_position": OPEN_POSITION,
            "supported_features": CoverEntityFeature.SET_POSITION,
        }
        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: None,  # Sun entity missing
            MOCK_COVER_ENTITY_ID: cover_state,  # Cover available
        }.get(entity_id)
        await sun_coordinator.async_refresh()
        assert isinstance(sun_coordinator.last_exception, UpdateFailed)
        assert "Sun integration not found" in str(sun_coordinator.last_exception)

    async def test_sun_automation_invalid_data(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test error when sun data is invalid."""
        mock_sun_state.attributes = {"elevation": "invalid", "azimuth": DIRECT_AZIMUTH}
        mock_hass.states.get.return_value = mock_sun_state
        await sun_coordinator.async_refresh()
        assert isinstance(sun_coordinator.last_exception, UpdateFailed)
        assert "Invalid sun position data" in str(sun_coordinator.last_exception)

    async def test_sun_automation_skips_unavailable_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """One unavailable cover should be skipped inside sun automation loop."""
        # Two covers configured; make second unavailable in the states mapping
        config = create_sun_config(
            covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2]
        )
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

        mock_sun_state.attributes = {
            "elevation": HIGH_ELEVATION,
            "azimuth": DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes["current_position"] = OPEN_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: None,  # Unavailable
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        # Only first cover should appear
        assert MOCK_COVER_ENTITY_ID in result["covers"]
        assert MOCK_COVER_ENTITY_ID_2 not in result["covers"]

    async def test_cover_unavailable(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test handling when all covers are unavailable."""
        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: None,
            MOCK_COVER_ENTITY_ID_2: None,
        }.get(entity_id)
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, EntityUnavailableError)

    async def test_service_call_failure(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test handling service call failures."""
        # Setup - temperature too hot, should close covers
        mock_temperature_state.state = HOT_TEMP
        mock_cover_state.attributes["current_position"] = OPEN_POSITION

        # Mock service call to fail
        mock_hass.services.async_call.side_effect = OSError("Service failed")

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute - should not raise exception, just log error
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify - automation still completes despite service failure
        assert result is not None
        assert MOCK_COVER_ENTITY_ID in result["covers"]

    async def test_cover_without_position_support(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test covers without position support."""
        # Setup cover without position support
        mock_cover_state.attributes["supported_features"] = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )
        mock_temperature_state.state = HOT_TEMP  # Too hot
        mock_cover_state.attributes["current_position"] = OPEN_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        await coordinator.async_refresh()

        # Verify close service called instead of set_position
        await assert_service_called(
            mock_hass.services,
            "cover",
            "close_cover",
            MOCK_COVER_ENTITY_ID,
        )

    async def test_invalid_automation_type(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Test error with invalid automation type."""
        config = create_temperature_config()
        config[CONF_AUTOMATION_TYPE] = "invalid_type"
        config_entry = MockConfigEntry(config)

        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)
        assert "Unknown automation type" in str(coordinator.last_exception)

    async def test_no_covers_configured(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when no covers are configured."""
        config = create_temperature_config()
        config[CONF_COVERS] = []
        config_entry = MockConfigEntry(config)

        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)
        assert "No covers configured" in str(coordinator.last_exception)

    async def test_angle_calculation(
        self,
        sun_coordinator: DataUpdateCoordinator,
    ) -> None:
        """Test angle difference calculation."""
        # Test direct alignment
        diff = sun_coordinator._calculate_angle_difference(
            DIRECT_AZIMUTH, DIRECT_AZIMUTH
        )
        assert diff == 0.0

        # Test 45 degree difference
        diff = sun_coordinator._calculate_angle_difference(DIRECT_AZIMUTH, 135.0)
        assert diff == 45.0

        # Test wraparound (0° and 350° should be 10° apart)
        diff = sun_coordinator._calculate_angle_difference(0.0, 350.0)
        assert diff == 10.0

    async def test_desired_position_calculation(
        self,
        sun_coordinator: DataUpdateCoordinator,
    ) -> None:
        """Test desired position calculation."""
        # Test low elevation
        pos = sun_coordinator._calculate_desired_position(
            LOW_ELEVATION,
            DIRECT_AZIMUTH,
            TILT_ANGLE,
            DIRECT_AZIMUTH,
            MOCK_COVER_ENTITY_ID,
        )
        assert pos == OPEN_POSITION  # Fully open

    async def test_sun_missing_cover_direction_skips_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """If a cover has no direction configured, it should be skipped."""
        # Build a sun config for two covers, remove direction for second cover
        config = create_sun_config(
            covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2]
        )
        # Remove direction for cover 2 to trigger skip
        config.pop(f"{MOCK_COVER_ENTITY_ID_2}_cover_direction", None)
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

        # Sun above threshold, direct hit
        mock_sun_state.attributes = {
            "elevation": HIGH_ELEVATION,
            "azimuth": DIRECT_AZIMUTH,
        }

        # Both covers available
        cover2_state = MagicMock()
        cover2_state.attributes = {
            "current_position": OPEN_POSITION,
            "supported_features": CoverEntityFeature.SET_POSITION,
        }

        mock_cover_state.attributes["current_position"] = OPEN_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: cover2_state,
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Only the properly configured cover should be in results
        assert MOCK_COVER_ENTITY_ID in result["covers"]
        assert MOCK_COVER_ENTITY_ID_2 not in result["covers"]

    async def test_sun_invalid_cover_direction_skips_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """If a cover has an invalid direction, it should be skipped."""
        config = create_sun_config(
            covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2]
        )
        # Set an invalid direction string for cover 2
        config[f"{MOCK_COVER_ENTITY_ID_2}_cover_direction"] = "upwards"
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

        mock_sun_state.attributes = {
            "elevation": HIGH_ELEVATION,
            "azimuth": DIRECT_AZIMUTH,
        }

        cover2_state = MagicMock()
        cover2_state.attributes = {
            "current_position": OPEN_POSITION,
            "supported_features": CoverEntityFeature.SET_POSITION,
        }
        mock_cover_state.attributes["current_position"] = OPEN_POSITION

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: cover2_state,
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Only the valid-direction cover should be present
        assert MOCK_COVER_ENTITY_ID in result["covers"]
        assert MOCK_COVER_ENTITY_ID_2 not in result["covers"]

    async def test_set_cover_position_warning_branch_no_features_partial(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """When cover lacks position and open/close for partial desired, no service is called."""
        config = create_sun_config()
        # Ensure direct-sun partial closure is not 100% (so desired != 0)
        config["max_closure"] = 90
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

        # Sun conditions to produce a partial desired position (10)
        mock_sun_state.attributes = {
            "elevation": HIGH_ELEVATION,
            "azimuth": DIRECT_AZIMUTH,
        }

        # Cover with no supported features
        cover_state = MagicMock()
        cover_state.attributes = {
            "current_position": OPEN_POSITION,  # 100
            "supported_features": 0,
        }

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: cover_state,
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Desired should be partial (10) but no service should be called
        assert result["covers"][MOCK_COVER_ENTITY_ID]["desired_position"] not in (
            OPEN_POSITION,
            CLOSED_POSITION,
        )
        mock_hass.services.async_call.assert_not_called()

    async def test_missing_config_keys_raise_configuration_error(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Missing required keys in config should raise ConfigurationError."""
        # Build a config missing the automation type key entirely
        config = {CONF_COVERS: [MOCK_COVER_ENTITY_ID]}
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(
            mock_hass, cast(IntegrationConfigEntry, config_entry)
        )

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)

    async def test_service_call_error_class_init(self) -> None:
        """Construct ServiceCallError to cover its initializer."""
        err = ServiceCallError("cover.set_cover_position", "cover.test", "boom")
        assert "Failed to call" in str(err)
        assert err.service == "cover.set_cover_position"
        assert err.entity_id == "cover.test"
