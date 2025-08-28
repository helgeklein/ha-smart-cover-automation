"""Tests for the Smart Cover Automation coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.smart_cover_automation.coordinator import (
    ConfigurationError,
    DataUpdateCoordinator,
    EntityUnavailableError,
    InvalidSensorReadingError,
    SensorNotFoundError,
)
from custom_components.smart_cover_automation.const import (
    AUTOMATION_TYPE_SUN,
    AUTOMATION_TYPE_TEMPERATURE,
    CONF_AUTOMATION_TYPE,
    CONF_COVERS,
)

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


class TestDataUpdateCoordinator:
    """Test DataUpdateCoordinator."""

    @pytest.fixture
    def coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a coordinator instance."""
        config_entry = MockConfigEntry(create_temperature_config())
        return DataUpdateCoordinator(mock_hass, config_entry)

    @pytest.fixture
    def sun_coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a sun coordinator instance."""
        config_entry = MockConfigEntry(create_sun_config())
        return DataUpdateCoordinator(mock_hass, config_entry)

    async def test_init(self, coordinator: DataUpdateCoordinator) -> None:
        """Test coordinator initialization."""
        assert coordinator.name == "smart_cover_automation"
        assert coordinator.config_entry is not None
        assert coordinator.update_interval.total_seconds() == 60

    async def test_temperature_automation_hot(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test temperature automation when too hot."""
        # Setup - temperature above maximum
        mock_temperature_state.state = "26.0"  # Above 24°C max
        mock_cover_state.attributes["current_position"] = 100  # Fully open

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        result = await coordinator._async_update_data()

        # Verify
        assert result is not None
        assert MOCK_COVER_ENTITY_ID in result["covers"]
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["current_temp"] == 26.0
        assert cover_data["desired_position"] == 0  # Should close

        # Verify service call
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=0,
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
        mock_temperature_state.state = "18.0"  # Below 21°C min
        mock_cover_state.attributes["current_position"] = 0  # Fully closed

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        result = await coordinator._async_update_data()

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["current_temp"] == 18.0
        assert cover_data["desired_position"] == 100  # Should open

        # Verify service call
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=100,
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
        mock_temperature_state.state = "22.5"  # Between 21-24°C
        mock_cover_state.attributes["current_position"] = 50

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        result = await coordinator._async_update_data()

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["current_temp"] == 22.5
        assert cover_data["desired_position"] == 50  # Should maintain

        # Verify no service call made
        mock_hass.services.async_call.assert_not_called()

    async def test_temperature_sensor_not_found(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when temperature sensor not found."""
        mock_hass.states.get.return_value = None

        with pytest.raises(SensorNotFoundError) as exc_info:
            await coordinator._async_update_data()

        assert "sensor.temperature" in str(exc_info.value)

    async def test_temperature_sensor_invalid_reading(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test error when temperature sensor has invalid reading."""
        mock_temperature_state.state = "invalid"
        mock_hass.states.get.return_value = mock_temperature_state

        with pytest.raises(InvalidSensorReadingError) as exc_info:
            await coordinator._async_update_data()

        assert "invalid" in str(exc_info.value)

    async def test_sun_automation_direct_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun automation with direct sunlight."""
        # Setup - sun directly south, high elevation
        mock_sun_state.attributes = {"elevation": 45.0, "azimuth": 180.0}
        mock_cover_state.attributes["current_position"] = 100

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        result = await sun_coordinator._async_update_data()

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["sun_elevation"] == 45.0
        assert cover_data["sun_azimuth"] == 180.0
        assert cover_data["desired_position"] == 10  # Should close to 90%

    async def test_sun_automation_low_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun automation with low sun elevation."""
        # Setup - sun below threshold
        mock_sun_state.attributes = {"elevation": 15.0, "azimuth": 180.0}
        mock_cover_state.attributes["current_position"] = 50

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_SUN_ENTITY_ID: mock_sun_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        result = await sun_coordinator._async_update_data()

        # Verify
        cover_data = result["covers"][MOCK_COVER_ENTITY_ID]
        assert cover_data["desired_position"] == 100  # Should open fully

    async def test_sun_automation_no_sun_entity(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when sun entity not found."""
        mock_hass.states.get.return_value = None

        with pytest.raises(UpdateFailed) as exc_info:
            await sun_coordinator._async_update_data()

        assert "Sun integration not found" in str(exc_info.value)

    async def test_sun_automation_invalid_data(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test error when sun data is invalid."""
        mock_sun_state.attributes = {"elevation": "invalid", "azimuth": 180.0}
        mock_hass.states.get.return_value = mock_sun_state

        with pytest.raises(UpdateFailed) as exc_info:
            await sun_coordinator._async_update_data()

        assert "Invalid sun position data" in str(exc_info.value)

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

        with pytest.raises(EntityUnavailableError):
            await coordinator._async_update_data()

    async def test_service_call_failure(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test handling service call failures."""
        # Setup - temperature too hot, should close covers
        mock_temperature_state.state = "26.0"
        mock_cover_state.attributes["current_position"] = 100

        # Mock service call to fail
        mock_hass.services.async_call.side_effect = OSError("Service failed")

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute - should not raise exception, just log error
        result = await coordinator._async_update_data()

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
        mock_temperature_state.state = "26.0"  # Too hot
        mock_cover_state.attributes["current_position"] = 100

        mock_hass.states.get.side_effect = lambda entity_id: {
            MOCK_TEMP_SENSOR_ENTITY_ID: mock_temperature_state,
            MOCK_COVER_ENTITY_ID: mock_cover_state,
            MOCK_COVER_ENTITY_ID_2: mock_cover_state,
        }.get(entity_id)

        # Execute
        await coordinator._async_update_data()

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

        coordinator = DataUpdateCoordinator(mock_hass, config_entry)

        with pytest.raises(ConfigurationError) as exc_info:
            await coordinator._async_update_data()

        assert "Unknown automation type" in str(exc_info.value)

    async def test_no_covers_configured(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when no covers are configured."""
        config = create_temperature_config()
        config[CONF_COVERS] = []
        config_entry = MockConfigEntry(config)

        coordinator = DataUpdateCoordinator(mock_hass, config_entry)

        with pytest.raises(ConfigurationError) as exc_info:
            await coordinator._async_update_data()

        assert "No covers configured" in str(exc_info.value)

    async def test_angle_calculation(
        self,
        sun_coordinator: DataUpdateCoordinator,
    ) -> None:
        """Test angle difference calculation."""
        # Test direct alignment
        diff = sun_coordinator._calculate_angle_difference(180.0, 180.0)
        assert diff == 0.0

        # Test 45 degree difference
        diff = sun_coordinator._calculate_angle_difference(180.0, 135.0)
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
        pos = sun_coordinator._calculate_desired_position(15.0, 180.0, 20.0, 180.0)
        assert pos == 100  # Fully open

        # Test direct sun hit
        pos = sun_coordinator._calculate_desired_position(45.0, 180.0, 20.0, 180.0)
        assert pos == 10  # 90% closed

        # Test sun not hitting window
        pos = sun_coordinator._calculate_desired_position(45.0, 180.0, 20.0, 90.0)
        assert pos == 100  # Fully open
