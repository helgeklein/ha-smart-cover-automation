"""Additional tests for binary sensor platform to achieve 100% coverage.

This module contains tests specifically designed to cover edge cases and
branches that aren't covered by the main test file.
"""

from __future__ import annotations

from typing import Iterable, cast

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    TempHotBinarySensor,
    WeatherSunnyBinarySensor,
)
from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.const import (
    BINARY_SENSOR_KEY_TEMP_HOT,
    BINARY_SENSOR_KEY_WEATHER_SUNNY,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


async def test_temp_hot_binary_sensor_with_hot_temperature(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test TempHotBinarySensor returns True when temperature is hot.

    This test verifies that the temp_hot binary sensor correctly reports True
    when the coordinator data indicates a hot day.
    """
    # Setup coordinator with hot temperature data
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator data with temp_hot = True
    coordinator.data = {"temp_hot": True}  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the temp_hot binary sensor
    temp_hot_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_TEMP_HOT),
        None,
    )
    assert temp_hot_entity is not None, "TempHot binary sensor not found"
    assert isinstance(temp_hot_entity, TempHotBinarySensor)
    assert temp_hot_entity.is_on is True


async def test_temp_hot_binary_sensor_with_cool_temperature(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test TempHotBinarySensor returns False when temperature is not hot.

    This test verifies that the temp_hot binary sensor correctly reports False
    when the coordinator data indicates temperature is below threshold.
    """
    # Setup coordinator with cool temperature data
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator data with temp_hot = False
    coordinator.data = {"temp_hot": False}  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the temp_hot binary sensor
    temp_hot_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_TEMP_HOT),
        None,
    )
    assert temp_hot_entity is not None, "TempHot binary sensor not found"
    assert isinstance(temp_hot_entity, TempHotBinarySensor)
    assert temp_hot_entity.is_on is False


async def test_temp_hot_binary_sensor_with_no_data(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test TempHotBinarySensor returns False when coordinator has no data.

    This test covers the else branch (lines 168-171) where coordinator.data is None
    or doesn't contain the temp_hot key.
    """
    # Setup coordinator with no data
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator with None data (initial state before first update)
    coordinator.data = None  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the temp_hot binary sensor
    temp_hot_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_TEMP_HOT),
        None,
    )
    assert temp_hot_entity is not None, "TempHot binary sensor not found"
    assert isinstance(temp_hot_entity, TempHotBinarySensor)
    # Should return False when no data available
    assert temp_hot_entity.is_on is False


async def test_temp_hot_binary_sensor_with_missing_key(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test TempHotBinarySensor returns False when temp_hot key is missing from data.

    This test covers the else branch where coordinator.data exists but doesn't
    contain the temp_hot key.
    """
    # Setup coordinator with data that doesn't contain temp_hot key
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator data without temp_hot key
    coordinator.data = {"covers": {}}  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the temp_hot binary sensor
    temp_hot_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_TEMP_HOT),
        None,
    )
    assert temp_hot_entity is not None, "TempHot binary sensor not found"
    assert isinstance(temp_hot_entity, TempHotBinarySensor)
    # Should return False when key is missing
    assert temp_hot_entity.is_on is False


async def test_weather_sunny_binary_sensor_with_sunny_weather(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test WeatherSunnyBinarySensor returns True when weather is sunny.

    This test verifies that the weather_sunny binary sensor correctly reports True
    when the coordinator data indicates sunny weather.
    """
    # Setup coordinator with sunny weather data
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator data with weather_sunny = True
    coordinator.data = {"weather_sunny": True}  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the weather_sunny binary sensor
    weather_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_WEATHER_SUNNY),
        None,
    )
    assert weather_entity is not None, "WeatherSunny binary sensor not found"
    assert isinstance(weather_entity, WeatherSunnyBinarySensor)
    assert weather_entity.is_on is True


async def test_weather_sunny_binary_sensor_with_cloudy_weather(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test WeatherSunnyBinarySensor returns False when weather is not sunny.

    This test verifies that the weather_sunny binary sensor correctly reports False
    when the coordinator data indicates cloudy or non-sunny weather.
    """
    # Setup coordinator with cloudy weather data
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator data with weather_sunny = False
    coordinator.data = {"weather_sunny": False}  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the weather_sunny binary sensor
    weather_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_WEATHER_SUNNY),
        None,
    )
    assert weather_entity is not None, "WeatherSunny binary sensor not found"
    assert isinstance(weather_entity, WeatherSunnyBinarySensor)
    assert weather_entity.is_on is False


async def test_weather_sunny_binary_sensor_with_no_data(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test WeatherSunnyBinarySensor returns False when coordinator has no data.

    This test covers the else branch (lines 203-206) where coordinator.data is None
    or doesn't contain the weather_sunny key.
    """
    # Setup coordinator with no data
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator with None data (initial state before first update)
    coordinator.data = None  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the weather_sunny binary sensor
    weather_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_WEATHER_SUNNY),
        None,
    )
    assert weather_entity is not None, "WeatherSunny binary sensor not found"
    assert isinstance(weather_entity, WeatherSunnyBinarySensor)
    # Should return False when no data available
    assert weather_entity.is_on is False


async def test_weather_sunny_binary_sensor_with_missing_key(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test WeatherSunnyBinarySensor returns False when weather_sunny key is missing.

    This test covers the else branch where coordinator.data exists but doesn't
    contain the weather_sunny key.
    """
    # Setup coordinator with data that doesn't contain weather_sunny key
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Mock coordinator data without weather_sunny key
    coordinator.data = {"covers": {}}  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:
        """Mock entity addition function."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Find the weather_sunny binary sensor
    weather_entity = next(
        (entity for entity in captured if entity.entity_description.key == BINARY_SENSOR_KEY_WEATHER_SUNNY),
        None,
    )
    assert weather_entity is not None, "WeatherSunny binary sensor not found"
    assert isinstance(weather_entity, WeatherSunnyBinarySensor)
    # Should return False when key is missing
    assert weather_entity.is_on is False
