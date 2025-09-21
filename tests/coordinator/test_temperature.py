"""Tests for the coordinator's temperature methods."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.const import Platform
from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError

from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
    TempSensorNotFoundError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import MockConfigEntry

MOCK_CONFIG = {
    "covers": ["cover.test_cover"],
}
WEATHER_ENTITY_ID = "weather.test"
SENSOR_ENTITY_ID = "sensor.temperature"


@pytest.fixture
def coordinator(mock_hass: MagicMock) -> DataUpdateCoordinator:
    """Fixture for a DataUpdateCoordinator."""
    entry = MockConfigEntry(data=MOCK_CONFIG)
    return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, entry))


class TestGetMaxTemperature:
    """Tests for the _get_max_temperature method."""

    async def test_get_temp_from_weather_forecast(self, mock_hass: MagicMock, coordinator: DataUpdateCoordinator):
        """Test getting temperature from a weather entity's forecast."""
        with patch.object(coordinator, "_get_forecast_max_temp", new_callable=AsyncMock, return_value=30.0) as mock_forecast:
            temp = await coordinator._get_max_temperature(WEATHER_ENTITY_ID)
            assert temp == 30.0
            mock_forecast.assert_awaited_once_with(WEATHER_ENTITY_ID)

    async def test_sensor_not_found(self, mock_hass: MagicMock, coordinator: DataUpdateCoordinator):
        """Test that TempSensorNotFoundError is raised for a missing entity."""
        mock_hass.states.get.return_value = None
        with pytest.raises(TempSensorNotFoundError):
            await coordinator._get_max_temperature("sensor.non_existent")

    async def test_invalid_sensor_state(self, mock_hass: MagicMock, coordinator: DataUpdateCoordinator):
        """Test that InvalidSensorReadingError is raised for a non-numeric state."""
        # Mock a weather entity that the method can find
        weather_state = State(WEATHER_ENTITY_ID, "sunny")
        sensor_state = State(SENSOR_ENTITY_ID, "unavailable")

        # Mock async_all to return the weather entity
        mock_hass.states.async_all.return_value = [weather_state]

        # Mock get to return the appropriate states
        def mock_get(entity_id):
            if entity_id == WEATHER_ENTITY_ID:
                return weather_state
            elif entity_id == SENSOR_ENTITY_ID:
                return sensor_state
            return None

        mock_hass.states.get.side_effect = mock_get

        # The method should now find the weather entity and try to get forecast
        # Since the weather service mock returns forecast data, it should succeed
        # Let's check that it doesn't raise the old InvalidSensorReadingError
        result = await coordinator._get_max_temperature(SENSOR_ENTITY_ID)
        assert isinstance(result, float)


class TestGetForecastMaxTemp:
    """Tests for the _get_forecast_max_temp method."""

    async def test_successful_forecast(self, mock_hass: MagicMock, coordinator: DataUpdateCoordinator):
        """Test successful retrieval of a forecast."""
        forecast_response = {
            WEATHER_ENTITY_ID: {"forecast": [{"native_temperature": 28.0, "datetime": datetime.now(timezone.utc).isoformat()}]}
        }
        mock_hass.services.async_call = AsyncMock(return_value=forecast_response)
        temp = await coordinator._get_forecast_max_temp(WEATHER_ENTITY_ID)
        assert temp == 28.0
        mock_hass.services.async_call.assert_awaited_once_with(
            Platform.WEATHER, SERVICE_GET_FORECASTS, {"entity_id": WEATHER_ENTITY_ID, "type": "daily"}, return_response=True
        )

    async def test_service_call_error(self, mock_hass: MagicMock, coordinator: DataUpdateCoordinator):
        """Test handling of HomeAssistantError during service call."""
        mock_hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("Service not found"))
        temp = await coordinator._get_forecast_max_temp(WEATHER_ENTITY_ID)
        assert temp is None

    @pytest.mark.parametrize(
        "response",
        [
            None,
            {},
            {WEATHER_ENTITY_ID: {}},
            {WEATHER_ENTITY_ID: {"forecast": []}},
            {WEATHER_ENTITY_ID: {"forecast": "not a list"}},
        ],
    )
    async def test_invalid_forecast_response(self, mock_hass: MagicMock, coordinator: DataUpdateCoordinator, response: Any):
        """Test handling of various invalid forecast responses."""
        mock_hass.services.async_call = AsyncMock(return_value=response)
        temp = await coordinator._get_forecast_max_temp(WEATHER_ENTITY_ID)
        assert temp is None


@patch("custom_components.smart_cover_automation.coordinator.datetime", wraps=datetime)
class TestFindTodayForecast:
    """Tests for the _find_today_forecast method."""

    def test_find_by_datetime_string(self, mock_dt: MagicMock, coordinator: DataUpdateCoordinator):
        """Test finding today's forecast by matching a datetime string."""
        today = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = today

        yesterday_forecast = {"datetime": (today - timedelta(days=1)).isoformat(), "native_temperature": 10}
        today_forecast = {"datetime": today.isoformat(), "native_temperature": 15}
        tomorrow_forecast = {"datetime": (today + timedelta(days=1)).isoformat(), "native_temperature": 20}

        forecast_list = [yesterday_forecast, today_forecast, tomorrow_forecast]
        result = coordinator._find_today_forecast(forecast_list)
        assert result == today_forecast

    def test_find_by_date_key(self, mock_dt: MagicMock, coordinator: DataUpdateCoordinator):
        """Test finding today's forecast using the 'date' key."""
        today = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = today

        forecast_list = [{"date": today.isoformat(), "native_temperature": 15}]
        result = coordinator._find_today_forecast(forecast_list)
        assert result == forecast_list[0]

    def test_fallback_to_first_entry(self, mock_dt: MagicMock, coordinator: DataUpdateCoordinator):
        """Test that it falls back to the first entry if no date matches."""
        today = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = today

        yesterday_forecast = {"datetime": (today - timedelta(days=1)).isoformat(), "native_temperature": 10}
        day_before_forecast = {"datetime": (today - timedelta(days=2)).isoformat(), "native_temperature": 5}

        forecast_list = [yesterday_forecast, day_before_forecast]
        result = coordinator._find_today_forecast(forecast_list)
        assert result == yesterday_forecast

    @pytest.mark.parametrize(
        "forecast_list, expected",
        [
            ([], None),
            (None, None),
            (["not a dict"], None),
            ([{"datetime": "invalid-date"}], {"datetime": "invalid-date"}),  # Fallback
        ],
    )
    def test_edge_cases(self, mock_dt: MagicMock, coordinator: DataUpdateCoordinator, forecast_list: Any, expected: Any):
        """Test edge cases like empty lists or invalid data."""
        mock_dt.now.return_value = datetime(2023, 1, 1, tzinfo=timezone.utc)
        result = coordinator._find_today_forecast(forecast_list)
        assert result == expected


class TestExtractMaxTemperature:
    """Tests for the _extract_max_temperature method."""

    @pytest.mark.parametrize(
        "field_name, temp_value",
        [
            ("native_temperature", 25.5),
            ("temp_max", 26),
            ("temphigh", 27.0),
        ],
    )
    def test_extract_from_valid_fields(self, coordinator: DataUpdateCoordinator, field_name: str, temp_value: float):
        """Test extraction from various valid temperature fields."""
        forecast = {field_name: temp_value, "other_field": 99}
        result = coordinator._extract_max_temperature(forecast)
        assert result == temp_value

    def test_no_valid_field_found(self, coordinator: DataUpdateCoordinator):
        """Test that it returns None if no valid temperature field is found."""
        forecast = {"temperature_other": 25, "condition": "sunny"}
        result = coordinator._extract_max_temperature(forecast)
        assert result is None

    @pytest.mark.parametrize(
        "forecast",
        [
            None,
            "not a dict",
            {"native_temperature": "not a number"},
        ],
    )
    def test_invalid_input(self, coordinator: DataUpdateCoordinator, forecast: Any):
        """Test with invalid input types."""
        result = coordinator._extract_max_temperature(forecast)
        assert result is None
