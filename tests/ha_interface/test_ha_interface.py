"""Comprehensive unit tests for HomeAssistantInterface class.

This module tests all methods of the HomeAssistantInterface class, which provides
a clean abstraction layer over Home Assistant's APIs. Tests cover:
- Cover control operations (set_cover_position)
- Weather and sensor data retrieval
- Sun data and state queries
- Temperature forecasting
- Logbook entry creation
- Error handling for various failure scenarios
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_CLOSE_COVER, SERVICE_OPEN_COVER, SERVICE_SET_COVER_POSITION, Platform
from homeassistant.exceptions import HomeAssistantError

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ResolvedConfig
from custom_components.smart_cover_automation.ha_interface import (
    HomeAssistantInterface,
    InvalidSensorReadingError,
    ServiceCallError,
    WeatherEntityNotFoundError,
)

if TYPE_CHECKING:
    pass

# Test constants
MOCK_COVER_ENTITY_ID = "cover.test_cover"
MOCK_WEATHER_ENTITY_ID = "weather.test"
TEST_UNIQUE_ID = "test_unique_id_123"


#
# Fixtures
#


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock HomeAssistant instance."""

    hass = MagicMock(spec=["services", "states", "config"])
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.config = MagicMock()
    hass.config.language = "en"
    return hass


@pytest.fixture
def mock_resolved_config() -> MagicMock:  # type: ignore[type-arg]
    """Create a mock ResolvedConfig."""

    config = MagicMock(spec=ResolvedConfig)
    config.simulation_mode = False
    config.weather_hot_cutover_time = time(16, 0)
    config.verbose_logging = False
    return config


@pytest.fixture
def resolved_settings_callback(mock_resolved_config: ResolvedConfig) -> MagicMock:  # type: ignore[type-arg]
    """Create a mock callback that returns resolved settings."""

    callback = MagicMock()
    callback.return_value = mock_resolved_config
    return callback


@pytest.fixture
def ha_interface(mock_hass: MagicMock, resolved_settings_callback: MagicMock) -> HomeAssistantInterface:  # type: ignore[type-arg]
    """Create a HomeAssistantInterface instance for testing."""

    interface = HomeAssistantInterface(mock_hass, resolved_settings_callback)  # type: ignore[arg-type]
    interface.status_sensor_unique_id = TEST_UNIQUE_ID
    return interface


#
# TestHomeAssistantInterfaceInitialization
#


class TestHomeAssistantInterfaceInitialization:
    """Test HomeAssistantInterface initialization."""

    #
    # test_initialization_with_valid_parameters
    #
    def test_initialization_with_valid_parameters(
        self,
        mock_hass: MagicMock,
        resolved_settings_callback: MagicMock,  # type: ignore[type-arg]
    ) -> None:
        """Test successful initialization with valid parameters."""

        interface = HomeAssistantInterface(mock_hass, resolved_settings_callback)  # type: ignore[arg-type]

        assert interface.hass == mock_hass
        assert interface._resolved_settings_callback == resolved_settings_callback
        assert interface.status_sensor_unique_id is None

    #
    # test_initialization_sets_unique_id
    #
    def test_initialization_sets_unique_id(
        self,
        mock_hass: MagicMock,
        resolved_settings_callback: MagicMock,  # type: ignore[type-arg]
    ) -> None:
        """Test that unique_id can be set after initialization."""

        interface = HomeAssistantInterface(mock_hass, resolved_settings_callback)  # type: ignore[arg-type]
        interface.status_sensor_unique_id = TEST_UNIQUE_ID

        assert interface.status_sensor_unique_id == TEST_UNIQUE_ID


#
# TestSetCoverPosition
#


class TestSetCoverPosition:
    """Test set_cover_position method."""

    #
    # test_set_position_with_position_support
    #
    async def test_set_position_with_position_support(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test setting cover position when SET_POSITION is supported."""

        features = CoverEntityFeature.SET_POSITION
        desired_pos = 75

        result = await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, desired_pos, int(features))

        assert result == desired_pos
        mock_hass.services.async_call.assert_called_once_with(
            Platform.COVER,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: MOCK_COVER_ENTITY_ID, ATTR_POSITION: desired_pos},
        )

    #
    # test_open_cover_without_position_support
    #
    async def test_open_cover_without_position_support(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test opening cover when SET_POSITION is not supported."""

        features = 0  # No position support
        desired_pos = 80  # > 50, should open

        result = await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, desired_pos, features)

        assert result == const.COVER_POS_FULLY_OPEN
        mock_hass.services.async_call.assert_called_once_with(Platform.COVER, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: MOCK_COVER_ENTITY_ID})

    #
    # test_close_cover_without_position_support
    #
    async def test_close_cover_without_position_support(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test closing cover when SET_POSITION is not supported."""

        features = 0  # No position support
        desired_pos = 20  # <= 50, should close

        result = await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, desired_pos, features)

        assert result == const.COVER_POS_FULLY_CLOSED
        mock_hass.services.async_call.assert_called_once_with(Platform.COVER, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: MOCK_COVER_ENTITY_ID})

    #
    # test_set_position_boundary_at_50_percent
    #
    async def test_set_position_boundary_at_50_percent(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test that exactly 50% without position support closes the cover."""

        features = 0  # No position support
        desired_pos = 50  # Exactly 50, should close

        result = await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, desired_pos, features)

        assert result == const.COVER_POS_FULLY_CLOSED
        mock_hass.services.async_call.assert_called_once_with(Platform.COVER, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: MOCK_COVER_ENTITY_ID})

    #
    # test_set_position_simulation_mode
    #
    async def test_set_position_simulation_mode(
        self,
        ha_interface: HomeAssistantInterface,
        mock_hass: MagicMock,
        mock_resolved_config: MagicMock,  # type: ignore[type-arg]
    ) -> None:
        """Test that service call is skipped in simulation mode."""

        mock_resolved_config.simulation_mode = True
        features = CoverEntityFeature.SET_POSITION
        desired_pos = 60

        result = await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, desired_pos, int(features))

        assert result == desired_pos
        mock_hass.services.async_call.assert_not_called()

    #
    # test_set_position_invalid_position_too_low
    #
    async def test_set_position_invalid_position_too_low(self, ha_interface: HomeAssistantInterface) -> None:
        """Test that invalid position (< 0) raises ValueError."""

        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ValueError, match="desired_pos must be between"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, -1, int(features))

    #
    # test_set_position_invalid_position_too_high
    #
    async def test_set_position_invalid_position_too_high(self, ha_interface: HomeAssistantInterface) -> None:
        """Test that invalid position (> 100) raises ValueError."""

        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ValueError, match="desired_pos must be between"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 101, int(features))

    #
    # test_set_position_oserror_handling
    #
    async def test_set_position_oserror_handling(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of OSError during service call."""

        mock_hass.services.async_call.side_effect = OSError("Network error")
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ServiceCallError, match="Failed to call"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 50, int(features))

    #
    # test_set_position_connection_error_handling
    #
    async def test_set_position_connection_error_handling(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of ConnectionError during service call."""

        mock_hass.services.async_call.side_effect = ConnectionError("Connection lost")
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ServiceCallError, match="Failed to call"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 50, int(features))

    #
    # test_set_position_timeout_error_handling
    #
    async def test_set_position_timeout_error_handling(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of TimeoutError during service call."""

        mock_hass.services.async_call.side_effect = TimeoutError("Request timeout")
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ServiceCallError, match="Failed to call"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 50, int(features))

    #
    # test_set_position_value_error_handling
    #
    async def test_set_position_value_error_handling(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of ValueError during service call."""

        mock_hass.services.async_call.side_effect = ValueError("Invalid value")
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ServiceCallError, match="Failed to call"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 50, int(features))

    #
    # test_set_position_type_error_handling
    #
    async def test_set_position_type_error_handling(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of TypeError during service call."""

        mock_hass.services.async_call.side_effect = TypeError("Type mismatch")
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ServiceCallError, match="Failed to call"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 50, int(features))

    #
    # test_set_position_generic_exception_handling
    #
    async def test_set_position_generic_exception_handling(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of unexpected exceptions during service call."""

        mock_hass.services.async_call.side_effect = RuntimeError("Unexpected error")
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ServiceCallError, match="Unexpected error"):
            await ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 50, int(features))


#
# TestGetWeatherCondition
#


class TestGetWeatherCondition:
    """Test get_weather_condition method."""

    #
    # test_get_weather_condition_success
    #
    def test_get_weather_condition_success(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test successfully retrieving weather condition."""

        mock_state = MagicMock()
        mock_state.state = "sunny"
        mock_hass.states.get.return_value = mock_state

        result = ha_interface.get_weather_condition(MOCK_WEATHER_ENTITY_ID)

        assert result == "sunny"
        mock_hass.states.get.assert_called_once_with(MOCK_WEATHER_ENTITY_ID)

    #
    # test_get_weather_condition_entity_not_found
    #
    def test_get_weather_condition_entity_not_found(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when weather entity does not exist."""

        mock_hass.states.get.return_value = None

        with pytest.raises(WeatherEntityNotFoundError, match=MOCK_WEATHER_ENTITY_ID):
            ha_interface.get_weather_condition(MOCK_WEATHER_ENTITY_ID)

    #
    # test_get_weather_condition_unavailable
    #
    def test_get_weather_condition_unavailable(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when weather condition is unavailable."""

        mock_state = MagicMock()
        mock_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_state

        with pytest.raises(InvalidSensorReadingError, match="state is unavailable"):
            ha_interface.get_weather_condition(MOCK_WEATHER_ENTITY_ID)

    #
    # test_get_weather_condition_unknown
    #
    def test_get_weather_condition_unknown(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when weather condition is unknown."""

        mock_state = MagicMock()
        mock_state.state = "unknown"
        mock_hass.states.get.return_value = mock_state

        with pytest.raises(InvalidSensorReadingError, match="state is unavailable"):
            ha_interface.get_weather_condition(MOCK_WEATHER_ENTITY_ID)

    #
    # test_get_weather_condition_none_state
    #
    def test_get_weather_condition_none_state(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when weather condition state is None."""

        mock_state = MagicMock()
        mock_state.state = None
        mock_hass.states.get.return_value = mock_state

        with pytest.raises(InvalidSensorReadingError, match="state is unavailable"):
            ha_interface.get_weather_condition(MOCK_WEATHER_ENTITY_ID)


#
# TestGetSunData
#


class TestGetSunData:
    """Test get_sun_data method."""

    #
    # test_get_sun_data_success
    #
    def test_get_sun_data_success(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test successfully retrieving sun azimuth and elevation."""

        mock_sun_state = MagicMock()
        mock_sun_state.attributes = {const.HA_SUN_ATTR_AZIMUTH: 180.5, const.HA_SUN_ATTR_ELEVATION: 45.3}
        mock_hass.states.get.return_value = mock_sun_state

        azimuth, elevation = ha_interface.get_sun_data()

        assert azimuth == 180.5
        assert elevation == 45.3
        mock_hass.states.get.assert_called_once_with(const.HA_SUN_ENTITY_ID)

    #
    # test_get_sun_data_entity_not_found
    #
    def test_get_sun_data_entity_not_found(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when sun entity does not exist."""

        from custom_components.smart_cover_automation.coordinator import SunSensorNotFoundError

        mock_hass.states.get.return_value = None

        with pytest.raises(SunSensorNotFoundError, match=const.HA_SUN_ENTITY_ID):
            ha_interface.get_sun_data()

    #
    # test_get_sun_data_elevation_unavailable
    #
    def test_get_sun_data_elevation_unavailable(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when sun elevation is unavailable."""

        mock_sun_state = MagicMock()
        mock_sun_state.attributes = {const.HA_SUN_ATTR_AZIMUTH: 180.0}  # Missing elevation
        mock_hass.states.get.return_value = mock_sun_state

        with pytest.raises(InvalidSensorReadingError, match="Sun elevation unavailable"):
            ha_interface.get_sun_data()

    #
    # test_get_sun_data_azimuth_defaults_to_zero
    #
    def test_get_sun_data_azimuth_defaults_to_zero(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test that azimuth defaults to 0 when missing."""

        mock_sun_state = MagicMock()
        mock_sun_state.attributes = {const.HA_SUN_ATTR_ELEVATION: 45.0}  # Missing azimuth
        mock_hass.states.get.return_value = mock_sun_state

        azimuth, elevation = ha_interface.get_sun_data()

        assert azimuth == 0.0
        assert elevation == 45.0

    #
    # test_get_sun_data_invalid_elevation_type
    #
    def test_get_sun_data_invalid_elevation_type(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when sun elevation is not a number."""

        mock_sun_state = MagicMock()
        mock_sun_state.attributes = {const.HA_SUN_ATTR_AZIMUTH: 180.0, const.HA_SUN_ATTR_ELEVATION: "invalid"}
        mock_hass.states.get.return_value = mock_sun_state

        with pytest.raises(InvalidSensorReadingError, match="Sun elevation unavailable"):
            ha_interface.get_sun_data()

    #
    # test_get_sun_data_invalid_azimuth_type
    #
    def test_get_sun_data_invalid_azimuth_type(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when sun azimuth is not a number."""

        mock_sun_state = MagicMock()
        mock_sun_state.attributes = {const.HA_SUN_ATTR_AZIMUTH: "invalid", const.HA_SUN_ATTR_ELEVATION: 45.0}
        mock_hass.states.get.return_value = mock_sun_state

        with pytest.raises(InvalidSensorReadingError, match="Sun azimuth unavailable"):
            ha_interface.get_sun_data()


#
# TestGetSunState
#


class TestGetSunState:
    """Test get_sun_state method."""

    #
    # test_get_sun_state_above_horizon
    #
    def test_get_sun_state_above_horizon(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test retrieving sun state when above horizon."""

        mock_sun_state = MagicMock()
        mock_sun_state.state = "above_horizon"
        mock_hass.states.get.return_value = mock_sun_state

        result = ha_interface.get_sun_state()

        assert result == "above_horizon"

    #
    # test_get_sun_state_below_horizon
    #
    def test_get_sun_state_below_horizon(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test retrieving sun state when below horizon."""

        mock_sun_state = MagicMock()
        mock_sun_state.state = "below_horizon"
        mock_hass.states.get.return_value = mock_sun_state

        result = ha_interface.get_sun_state()

        assert result == "below_horizon"

    #
    # test_get_sun_state_entity_not_found
    #
    def test_get_sun_state_entity_not_found(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test that None is returned when sun entity does not exist."""

        mock_hass.states.get.return_value = None

        result = ha_interface.get_sun_state()

        assert result is None


#
# TestGetEntityState
#


class TestGetEntityState:
    """Test get_entity_state method."""

    #
    # test_get_entity_state_success
    #
    def test_get_entity_state_success(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test successfully retrieving entity state."""

        mock_state = MagicMock()
        mock_state.state = "on"
        mock_hass.states.get.return_value = mock_state

        result = ha_interface.get_entity_state("switch.test")

        assert result == "on"

    #
    # test_get_entity_state_not_found
    #
    def test_get_entity_state_not_found(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test that None is returned when entity does not exist."""

        mock_hass.states.get.return_value = None

        result = ha_interface.get_entity_state("switch.nonexistent")

        assert result is None


#
# TestGetMaxTemperature
#


class TestGetMaxTemperature:
    """Test get_max_temperature method."""

    #
    # test_get_max_temperature_success
    #
    async def test_get_max_temperature_success(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test successfully retrieving maximum temperature from forecast."""

        mock_weather_state = MagicMock()
        mock_hass.states.get.return_value = mock_weather_state

        # Get applicable date for forecast (use today before cutover time)
        now = datetime.now(timezone.utc)
        today = now.date()
        forecast_datetime = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        # Mock the weather service response
        mock_hass.services.async_call.return_value = {
            MOCK_WEATHER_ENTITY_ID: {"forecast": [{"datetime": forecast_datetime.isoformat(), "native_temperature": 28.5}]}
        }

        with patch("homeassistant.util.dt.now") as mock_now:
            # Mock time before cutover (10:00 AM) to use today's forecast
            mock_now.return_value = datetime.combine(today, time(10, 0), tzinfo=timezone.utc)

            result = await ha_interface.get_max_temperature(MOCK_WEATHER_ENTITY_ID)

        assert result == 28.5

    #
    # test_get_max_temperature_entity_not_found
    #
    async def test_get_max_temperature_entity_not_found(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when weather entity does not exist."""

        mock_hass.states.get.return_value = None

        with pytest.raises(WeatherEntityNotFoundError, match=MOCK_WEATHER_ENTITY_ID):
            await ha_interface.get_max_temperature(MOCK_WEATHER_ENTITY_ID)

    #
    # test_get_max_temperature_forecast_unavailable
    #
    async def test_get_max_temperature_forecast_unavailable(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when forecast is unavailable."""

        mock_weather_state = MagicMock()
        mock_hass.states.get.return_value = mock_weather_state

        # Mock service returning None
        mock_hass.services.async_call.return_value = None

        with pytest.raises(InvalidSensorReadingError, match="Forecast temperature unavailable"):
            await ha_interface.get_max_temperature(MOCK_WEATHER_ENTITY_ID)

    #
    # test_get_max_temperature_empty_forecast
    #
    async def test_get_max_temperature_empty_forecast(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test error when forecast list is empty."""

        mock_weather_state = MagicMock()
        mock_hass.states.get.return_value = mock_weather_state

        # Mock service returning empty forecast
        mock_hass.services.async_call.return_value = {MOCK_WEATHER_ENTITY_ID: {"forecast": []}}

        with pytest.raises(InvalidSensorReadingError, match="Forecast temperature unavailable"):
            await ha_interface.get_max_temperature(MOCK_WEATHER_ENTITY_ID)

    #
    # test_get_max_temperature_fahrenheit
    #
    async def test_get_max_temperature_fahrenheit(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test successfully retrieving maximum temperature from Fahrenheit forecast."""
        from homeassistant.components.weather.const import ATTR_WEATHER_TEMPERATURE_UNIT
        from homeassistant.const import UnitOfTemperature

        mock_weather_state = MagicMock()
        mock_weather_state.attributes = {ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT}
        mock_hass.states.get.return_value = mock_weather_state

        # Get applicable date for forecast (use today before cutover time)
        now = datetime.now(timezone.utc)
        today = now.date()
        forecast_datetime = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        # Mock the weather service response with Fahrenheit value (80.6 F ~ 27 C)
        mock_hass.services.async_call.return_value = {
            MOCK_WEATHER_ENTITY_ID: {"forecast": [{"datetime": forecast_datetime.isoformat(), "native_temperature": 80.6}]}
        }

        with patch("homeassistant.util.dt.now") as mock_now:
            # Mock time before cutover (10:00 AM) to use today's forecast
            mock_now.return_value = datetime.combine(today, time(10, 0), tzinfo=timezone.utc)

            result = await ha_interface.get_max_temperature(MOCK_WEATHER_ENTITY_ID)

        # Expect conversion to Celsius: (80.6 - 32) * 5/9 = 27.0
        assert result == pytest.approx(27.0)


#
# TestFindDayForecast
#


class TestFindDayForecast:
    """Test _find_day_forecast method."""

    #
    # test_find_day_forecast_today_before_cutover
    #
    def test_find_day_forecast_today_before_cutover(
        self,
        ha_interface: HomeAssistantInterface,
        mock_resolved_config: MagicMock,  # type: ignore[type-arg]
    ) -> None:
        """Test finding today's forecast before cutover time."""

        mock_resolved_config.weather_hot_cutover_time = time(16, 0)

        # Create forecast for today
        now = datetime.now(timezone.utc)
        today = now.date()
        forecast_datetime = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        forecast_list = [{"datetime": forecast_datetime.isoformat(), "native_temperature": 25.0}]

        with patch("homeassistant.util.dt.now") as mock_now:
            # Mock time before cutover (10:00 AM)
            mock_now.return_value = datetime.combine(today, time(10, 0), tzinfo=timezone.utc)

            result = ha_interface._find_day_forecast(forecast_list)

        assert result is not None
        day_name, forecast = result
        assert day_name == "today"
        assert forecast["native_temperature"] == 25.0

    #
    # test_find_day_forecast_tomorrow_after_cutover
    #
    def test_find_day_forecast_tomorrow_after_cutover(
        self,
        ha_interface: HomeAssistantInterface,
        mock_resolved_config: MagicMock,  # type: ignore[type-arg]
    ) -> None:
        """Test finding tomorrow's forecast after cutover time."""

        mock_resolved_config.weather_hot_cutover_time = time(16, 0)

        # Create forecast for tomorrow
        now = datetime.now(timezone.utc)
        tomorrow = now.date() + timedelta(days=1)
        forecast_datetime = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)

        forecast_list = [{"datetime": forecast_datetime.isoformat(), "native_temperature": 30.0}]

        with patch("homeassistant.util.dt.now") as mock_now:
            # Mock time after cutover (18:00)
            mock_now.return_value = datetime.combine(now.date(), time(18, 0), tzinfo=timezone.utc)

            result = ha_interface._find_day_forecast(forecast_list)

        assert result is not None
        day_name, forecast = result
        assert day_name == "tomorrow"
        assert forecast["native_temperature"] == 30.0

    #
    # test_find_day_forecast_empty_list
    #
    def test_find_day_forecast_empty_list(self, ha_interface: HomeAssistantInterface) -> None:
        """Test that None is returned for empty forecast list."""

        result = ha_interface._find_day_forecast([])

        assert result is None

    #
    # test_find_day_forecast_invalid_datetime
    #
    def test_find_day_forecast_invalid_datetime(self, ha_interface: HomeAssistantInterface) -> None:
        """Test handling of invalid datetime in forecast."""

        forecast_list = [{"datetime": "invalid-date", "native_temperature": 25.0}]

        result = ha_interface._find_day_forecast(forecast_list)

        assert result is None

    #
    # test_find_day_forecast_missing_datetime
    #
    def test_find_day_forecast_missing_datetime(self, ha_interface: HomeAssistantInterface) -> None:
        """Test handling of missing datetime field in forecast."""

        forecast_list = [{"native_temperature": 25.0}]  # Missing datetime

        result = ha_interface._find_day_forecast(forecast_list)

        assert result is None

    #
    # test_find_day_forecast_datetime_object
    #
    def test_find_day_forecast_datetime_object(self, ha_interface: HomeAssistantInterface) -> None:
        """Test finding forecast with datetime object (not string)."""

        now = datetime.now(timezone.utc)
        today = now.date()
        forecast_datetime = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        forecast_list = [{"datetime": forecast_datetime, "native_temperature": 25.0}]

        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime.combine(today, time(10, 0), tzinfo=timezone.utc)

            result = ha_interface._find_day_forecast(forecast_list)

        assert result is not None
        assert result[1]["native_temperature"] == 25.0


#
# TestExtractMaxTemperature
#


class TestExtractMaxTemperature:
    """Test _extract_max_temperature method."""

    #
    # test_extract_max_temperature_native_temperature
    #
    def test_extract_max_temperature_native_temperature(self, ha_interface: HomeAssistantInterface) -> None:
        """Test extracting temperature from native_temperature field."""

        forecast = {"native_temperature": 28.5}

        result = ha_interface._extract_max_temperature(forecast)

        assert result == 28.5

    #
    # test_extract_max_temperature_temperature
    #
    def test_extract_max_temperature_temperature(self, ha_interface: HomeAssistantInterface) -> None:
        """Test extracting temperature from temperature field."""

        forecast = {"temperature": 26.0}

        result = ha_interface._extract_max_temperature(forecast)

        assert result == 26.0

    #
    # test_extract_max_temperature_temp_max
    #
    def test_extract_max_temperature_temp_max(self, ha_interface: HomeAssistantInterface) -> None:
        """Test extracting temperature from temp_max field."""

        forecast = {"temp_max": 30.0}

        result = ha_interface._extract_max_temperature(forecast)

        assert result == 30.0

    #
    # test_extract_max_temperature_temp_high
    #
    def test_extract_max_temperature_temp_high(self, ha_interface: HomeAssistantInterface) -> None:
        """Test extracting temperature from temp_high field."""

        forecast = {"temp_high": 29.0}

        result = ha_interface._extract_max_temperature(forecast)

        assert result == 29.0

    #
    # test_extract_max_temperature_priority_order
    #
    def test_extract_max_temperature_priority_order(self, ha_interface: HomeAssistantInterface) -> None:
        """Test that native_temperature takes priority over other fields."""

        forecast = {"native_temperature": 28.0, "temperature": 26.0, "temp_max": 30.0}

        result = ha_interface._extract_max_temperature(forecast)

        assert result == 28.0

    #
    # test_extract_max_temperature_integer_value
    #
    def test_extract_max_temperature_integer_value(self, ha_interface: HomeAssistantInterface) -> None:
        """Test extracting integer temperature value."""

        forecast = {"native_temperature": 25}

        result = ha_interface._extract_max_temperature(forecast)

        assert result == 25.0
        assert isinstance(result, float)

    #
    # test_extract_max_temperature_not_found
    #
    def test_extract_max_temperature_not_found(self, ha_interface: HomeAssistantInterface) -> None:
        """Test that None is returned when no temperature field is found."""

        forecast = {"humidity": 60, "precipitation": 0}

        result = ha_interface._extract_max_temperature(forecast)

        assert result is None

    #
    # test_extract_max_temperature_invalid_type
    #
    def test_extract_max_temperature_invalid_type(self, ha_interface: HomeAssistantInterface) -> None:
        """Test that None is returned for non-numeric temperature value."""

        forecast = {"native_temperature": "twenty-five"}

        result = ha_interface._extract_max_temperature(forecast)

        assert result is None

    #
    # test_extract_max_temperature_non_dict_input
    #
    def test_extract_max_temperature_non_dict_input(self, ha_interface: HomeAssistantInterface) -> None:
        """Test that None is returned for non-dict input."""

        result = ha_interface._extract_max_temperature("not a dict")  # type: ignore[arg-type]

        assert result is None


#
# TestAddLogbookEntry
#


class TestAddLogbookEntry:
    """Test add_logbook_entry method."""

    #
    # test_add_logbook_entry_success
    #
    async def test_add_logbook_entry_success(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test successfully adding a logbook entry."""

        with (
            patch("custom_components.smart_cover_automation.ha_interface.ha_entity_registry.async_get") as mock_registry,
            patch("custom_components.smart_cover_automation.ha_interface.translation.async_get_translations") as mock_translations,
            patch("custom_components.smart_cover_automation.ha_interface.async_log_entry") as mock_log_entry,
        ):
            # Mock entity registry
            mock_entity = MagicMock()
            mock_entity.unique_id = TEST_UNIQUE_ID
            mock_entity.entity_id = "binary_sensor.smart_cover_status"
            mock_entity.platform = const.DOMAIN

            mock_reg = MagicMock()
            mock_reg.entities.values.return_value = [mock_entity]
            mock_registry.return_value = mock_reg

            # Mock translations
            mock_translations.return_value = {
                f"component.{const.DOMAIN}.{const.TRANSL_KEY_SERVICES}.{const.SERVICE_LOGBOOK_ENTRY}.{const.TRANSL_KEY_FIELDS}.opening.{const.TRANSL_ATTR_NAME}": "Opening",
                f"component.{const.DOMAIN}.{const.TRANSL_KEY_SERVICES}.{const.SERVICE_LOGBOOK_ENTRY}.{const.TRANSL_KEY_FIELDS}.sun_hitting.{const.TRANSL_ATTR_NAME}": "sun hitting",
                f"component.{const.DOMAIN}.{const.TRANSL_KEY_SERVICES}.{const.SERVICE_LOGBOOK_ENTRY}.{const.TRANSL_KEY_FIELDS}.{const.TRANSL_LOGBOOK_TEMPLATE_COVER_MOVEMENT}.{const.TRANSL_ATTR_NAME}": "{verb} {entity_id} to {position}% because {reason}",
            }

            await ha_interface.add_logbook_entry("opening", MOCK_COVER_ENTITY_ID, "sun_hitting", 50)

            # Verify log entry was called
            mock_log_entry.assert_called_once()
            call_args = mock_log_entry.call_args
            assert call_args.kwargs["domain"] == const.DOMAIN
            assert call_args.kwargs["name"] == const.INTEGRATION_NAME
            assert MOCK_COVER_ENTITY_ID in call_args.kwargs["message"]

    #
    # test_add_logbook_entry_entity_not_found
    #
    async def test_add_logbook_entry_entity_not_found(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling when integration entity is not found."""

        with patch("custom_components.smart_cover_automation.ha_interface.ha_entity_registry.async_get") as mock_registry:
            # Mock empty entity registry
            mock_reg = MagicMock()
            mock_reg.entities.values.return_value = []
            mock_registry.return_value = mock_reg

            # Should not raise exception, just log warning
            await ha_interface.add_logbook_entry("opening", MOCK_COVER_ENTITY_ID, "sun_hitting", 50)

    #
    # test_add_logbook_entry_missing_translations
    #
    async def test_add_logbook_entry_missing_translations(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling when translations are missing."""

        with (
            patch("custom_components.smart_cover_automation.ha_interface.ha_entity_registry.async_get") as mock_registry,
            patch("custom_components.smart_cover_automation.ha_interface.translation.async_get_translations") as mock_translations,
            patch("custom_components.smart_cover_automation.ha_interface.async_log_entry") as mock_log_entry,
        ):
            # Mock entity registry
            mock_entity = MagicMock()
            mock_entity.unique_id = TEST_UNIQUE_ID
            mock_entity.entity_id = "binary_sensor.smart_cover_status"
            mock_entity.platform = const.DOMAIN

            mock_reg = MagicMock()
            mock_reg.entities.values.return_value = [mock_entity]
            mock_registry.return_value = mock_reg

            # Mock incomplete translations
            mock_translations.return_value = {}

            # Should not raise exception
            await ha_interface.add_logbook_entry("opening", MOCK_COVER_ENTITY_ID, "sun_hitting", 50)

            # Log entry should not be called
            mock_log_entry.assert_not_called()

    #
    # test_add_logbook_entry_exception_handling
    #
    async def test_add_logbook_entry_exception_handling(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test that exceptions in logbook entry don't break automation."""

        with patch("custom_components.smart_cover_automation.ha_interface.ha_entity_registry.async_get") as mock_registry:
            mock_registry.side_effect = RuntimeError("Registry error")

            # Should not raise exception
            await ha_interface.add_logbook_entry("opening", MOCK_COVER_ENTITY_ID, "sun_hitting", 50)


#
# TestGetForecastMaxTemp
#


class TestGetForecastMaxTemp:
    """Test _get_forecast_max_temp method."""

    #
    # test_get_forecast_max_temp_success
    #
    async def test_get_forecast_max_temp_success(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test successfully retrieving forecast temperature."""

        now = datetime.now(timezone.utc)
        today = now.date()
        forecast_datetime = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

        mock_hass.services.async_call.return_value = {
            MOCK_WEATHER_ENTITY_ID: {"forecast": [{"datetime": forecast_datetime.isoformat(), "native_temperature": 27.5}]}
        }

        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime.combine(today, time(10, 0), tzinfo=timezone.utc)

            result = await ha_interface._get_forecast_max_temp(MOCK_WEATHER_ENTITY_ID)

        assert result == 27.5

    #
    # test_get_forecast_max_temp_service_error
    #
    async def test_get_forecast_max_temp_service_error(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of HomeAssistantError from weather service."""

        mock_hass.services.async_call.side_effect = HomeAssistantError("Service call failed")

        result = await ha_interface._get_forecast_max_temp(MOCK_WEATHER_ENTITY_ID)

        assert result is None

    #
    # test_get_forecast_max_temp_invalid_response
    #
    async def test_get_forecast_max_temp_invalid_response(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of invalid response structure."""

        mock_hass.services.async_call.return_value = {"wrong_key": {}}

        result = await ha_interface._get_forecast_max_temp(MOCK_WEATHER_ENTITY_ID)

        assert result is None

    #
    # test_get_forecast_max_temp_missing_forecast_key
    #
    async def test_get_forecast_max_temp_missing_forecast_key(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of missing forecast key in response."""

        mock_hass.services.async_call.return_value = {MOCK_WEATHER_ENTITY_ID: {}}

        result = await ha_interface._get_forecast_max_temp(MOCK_WEATHER_ENTITY_ID)

        assert result is None

    #
    # test_get_forecast_max_temp_empty_forecast_list
    #
    async def test_get_forecast_max_temp_empty_forecast_list(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of empty forecast list."""

        mock_hass.services.async_call.return_value = {MOCK_WEATHER_ENTITY_ID: {"forecast": []}}

        result = await ha_interface._get_forecast_max_temp(MOCK_WEATHER_ENTITY_ID)

        assert result is None

    #
    # test_get_forecast_max_temp_generic_exception
    #
    async def test_get_forecast_max_temp_generic_exception(self, ha_interface: HomeAssistantInterface, mock_hass: MagicMock) -> None:
        """Test handling of unexpected exception."""

        mock_hass.services.async_call.side_effect = RuntimeError("Unexpected error")

        result = await ha_interface._get_forecast_max_temp(MOCK_WEATHER_ENTITY_ID)

        assert result is None
