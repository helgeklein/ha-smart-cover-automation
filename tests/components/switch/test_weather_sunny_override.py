"""Tests for the WeatherSunnyExternalControlSwitch entity.

This module tests the weather sunny override switch, which allows external
sunlight sensors to control the integration's "sun is shining" state.

Tests cover:
- Switch initialization and entity properties
- Turn on/off behavior and config option persistence
- Cleanup on entity removal (async_will_remove_from_hass)
- Entity registry disabled-by-default behavior
- Override logic in the automation engine
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from custom_components.smart_cover_automation.config import ConfKeys, resolve
from custom_components.smart_cover_automation.const import (
    COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL,
    SWITCH_KEY_COVER_WEATHER_HOT_EXTERNAL_CONTROL,
    SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL,
    SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL,
)
from custom_components.smart_cover_automation.switch import (
    CoverWeatherHotExternalControlSwitch,
    WeatherHotExternalControlSwitch,
    WeatherSunnyExternalControlSwitch,
)
from tests.conftest import MOCK_WEATHER_ENTITY_ID


@pytest.fixture
def override_switch(mock_coordinator_basic) -> WeatherSunnyExternalControlSwitch:
    """Create a WeatherSunnyExternalControlSwitch for testing.

    Returns:
        WeatherSunnyExternalControlSwitch instance bound to the basic coordinator
    """

    return WeatherSunnyExternalControlSwitch(mock_coordinator_basic)


@pytest.fixture
def hot_override_switch(mock_coordinator_basic) -> WeatherHotExternalControlSwitch:
    """Create a WeatherHotExternalControlSwitch for testing."""

    return WeatherHotExternalControlSwitch(mock_coordinator_basic)


@pytest.fixture
def cover_hot_override_switch(mock_coordinator_basic) -> CoverWeatherHotExternalControlSwitch:
    """Create a per-cover WeatherHotExternalControlSwitch for testing."""

    return CoverWeatherHotExternalControlSwitch(mock_coordinator_basic, "cover.test_cover")


class TestWeatherSunnyOverrideSwitchInit:
    """Test WeatherSunnyExternalControlSwitch initialization."""

    def test_unique_id(self, override_switch, mock_coordinator_basic) -> None:
        """Test that the unique ID is set correctly."""

        entry_id = mock_coordinator_basic.config_entry.entry_id
        assert override_switch.unique_id == f"{entry_id}_{SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL}"

    def test_entity_registry_disabled_by_default(self, override_switch) -> None:
        """Test that the entity is disabled by default in the entity registry."""

        assert override_switch._attr_entity_registry_enabled_default is False

    def test_entity_description_key(self, override_switch) -> None:
        """Test that the entity description key is correct."""

        assert override_switch.entity_description.key == SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL

    def test_entity_description_translation_key(self, override_switch) -> None:
        """Test that the translation key is correct."""

        assert override_switch.entity_description.translation_key == SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL

    def test_entity_description_icon(self, override_switch) -> None:
        """Test that the icon is set correctly."""

        assert override_switch.entity_description.icon == "mdi:weather-sunny-alert"


class TestWeatherSunnyOverrideSwitchState:
    """Test WeatherSunnyExternalControlSwitch state reading."""

    def test_is_on_returns_false_when_key_absent(self, override_switch) -> None:
        """Test that is_on returns False when the override key is not in options."""

        # Key not present → default False
        assert override_switch.is_on is False

    def test_is_on_returns_true_when_override_true(self, override_switch) -> None:
        """Test that is_on returns True when the override is set to True."""

        override_switch.coordinator.config_entry.options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] = True
        assert override_switch.is_on is True

    def test_is_on_returns_false_when_override_false(self, override_switch) -> None:
        """Test that is_on returns False when the override is set to False."""

        override_switch.coordinator.config_entry.options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] = False
        assert override_switch.is_on is False


class TestWeatherHotOverrideSwitchInit:
    """Test WeatherHotExternalControlSwitch initialization."""

    def test_unique_id(self, hot_override_switch, mock_coordinator_basic) -> None:
        """Test that the unique ID is set correctly."""

        entry_id = mock_coordinator_basic.config_entry.entry_id
        assert hot_override_switch.unique_id == f"{entry_id}_{SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL}"

    def test_entity_registry_disabled_by_default(self, hot_override_switch) -> None:
        """Test that the entity is disabled by default in the entity registry."""

        assert hot_override_switch._attr_entity_registry_enabled_default is False

    def test_entity_description_key(self, hot_override_switch) -> None:
        """Test that the entity description key is correct."""

        assert hot_override_switch.entity_description.key == SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL

    def test_entity_description_translation_key(self, hot_override_switch) -> None:
        """Test that the translation key is correct."""

        assert hot_override_switch.entity_description.translation_key == SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL


class TestCoverWeatherHotOverrideSwitchInit:
    """Test CoverWeatherHotExternalControlSwitch initialization."""

    def test_unique_id(self, cover_hot_override_switch, mock_coordinator_basic) -> None:
        """Test that the unique ID is set correctly."""

        entry_id = mock_coordinator_basic.config_entry.entry_id
        expected_key = f"cover.test_cover_{COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"
        assert cover_hot_override_switch.unique_id == f"{entry_id}_{expected_key}"

    def test_name_is_not_hard_coded(self, cover_hot_override_switch) -> None:
        """Test that the visible name is resolved via translations, not hard-coded."""

        assert getattr(cover_hot_override_switch, "_attr_name", None) is None

    def test_entity_description_key(self, cover_hot_override_switch) -> None:
        """Test that the config key is per-cover specific."""

        expected_key = f"cover.test_cover_{COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"
        assert cover_hot_override_switch.entity_description.key == expected_key

    def test_entity_description_translation_key(self, cover_hot_override_switch) -> None:
        """Test that the per-cover switch uses its dedicated translation key."""

        assert cover_hot_override_switch.entity_description.translation_key == SWITCH_KEY_COVER_WEATHER_HOT_EXTERNAL_CONTROL

    def test_translation_placeholders_include_cover_name(self, cover_hot_override_switch) -> None:
        """Test that the translated name receives the dynamic cover name."""

        assert cover_hot_override_switch.translation_placeholders == {"cover_name": "Test Cover"}


class TestWeatherHotOverrideSwitchState:
    """Test WeatherHotExternalControlSwitch state reading."""

    def test_is_on_returns_false_when_key_absent(self, hot_override_switch) -> None:
        """Test that is_on returns False when the override key is not in options."""

        assert hot_override_switch.is_on is False

    def test_is_on_returns_true_when_override_true(self, hot_override_switch) -> None:
        """Test that is_on returns True when the override is set to True."""

        hot_override_switch.coordinator.config_entry.options[SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL] = True
        assert hot_override_switch.is_on is True


class TestCoverWeatherHotOverrideSwitchState:
    """Test CoverWeatherHotExternalControlSwitch state reading."""

    def test_is_on_returns_false_when_key_absent(self, cover_hot_override_switch) -> None:
        """Test that is_on returns False when the per-cover override key is absent."""

        assert cover_hot_override_switch.is_on is False

    def test_is_on_returns_true_when_override_true(self, cover_hot_override_switch) -> None:
        """Test that is_on returns True when the per-cover override is set to True."""

        cover_hot_override_switch.coordinator.config_entry.options[f"cover.test_cover_{COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"] = True
        assert cover_hot_override_switch.is_on is True


class TestWeatherSunnyOverrideSwitchLifecycle:
    """Test WeatherSunnyExternalControlSwitch lifecycle hooks."""

    async def test_added_to_hass_seeds_default_override_when_key_absent(self, override_switch) -> None:
        """Test that enabling the entity seeds the default override when the key is absent."""

        override_switch._async_persist_override = AsyncMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
            new=AsyncMock(),
        ):
            await override_switch.async_added_to_hass()

        override_switch._async_persist_override.assert_awaited_once_with(False)

    async def test_added_to_hass_does_not_overwrite_existing_override(self, override_switch) -> None:
        """Test that enabling the entity does not overwrite an existing override value."""

        override_switch.coordinator.config_entry.options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] = True
        override_switch._async_persist_override = AsyncMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
            new=AsyncMock(),
        ):
            await override_switch.async_added_to_hass()

        override_switch._async_persist_override.assert_not_awaited()


class TestWeatherHotOverrideSwitchLifecycle:
    """Test WeatherHotExternalControlSwitch lifecycle hooks."""

    async def test_added_to_hass_seeds_default_override_when_key_absent(self, hot_override_switch) -> None:
        """Test that enabling the entity seeds the default override when the key is absent."""

        hot_override_switch._async_persist_override = AsyncMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
            new=AsyncMock(),
        ):
            await hot_override_switch.async_added_to_hass()

        hot_override_switch._async_persist_override.assert_awaited_once_with(False)


class TestCoverWeatherHotOverrideSwitchLifecycle:
    """Test CoverWeatherHotExternalControlSwitch lifecycle hooks."""

    async def test_added_to_hass_seeds_default_override_when_key_absent(self, cover_hot_override_switch) -> None:
        """Test that enabling the entity seeds the default override when the key is absent."""

        cover_hot_override_switch._async_persist_override = AsyncMock()

        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_added_to_hass",
            new=AsyncMock(),
        ):
            await cover_hot_override_switch.async_added_to_hass()

        cover_hot_override_switch._async_persist_override.assert_awaited_once_with(False)


class TestWeatherSunnyOverrideSwitchToggle:
    """Test WeatherSunnyExternalControlSwitch turn on/off behavior."""

    async def test_turn_on_persists_true(self, override_switch) -> None:
        """Test that turning the switch ON persists True to config options."""

        override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await override_switch.async_turn_on()

        # Verify async_update_entry was called with the override set to True
        override_switch.coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = override_switch.coordinator.hass.config_entries.async_update_entry.call_args
        options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
        assert options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] is True

    async def test_turn_off_persists_false(self, override_switch) -> None:
        """Test that turning the switch OFF persists False to config options."""

        override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await override_switch.async_turn_off()

        # Verify async_update_entry was called with the override set to False
        override_switch.coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = override_switch.coordinator.hass.config_entries.async_update_entry.call_args
        options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
        assert options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] is False


class TestWeatherHotOverrideSwitchToggle:
    """Test WeatherHotExternalControlSwitch turn on/off behavior."""

    async def test_turn_on_persists_true(self, hot_override_switch) -> None:
        """Test that turning the switch ON persists True to config options."""

        hot_override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await hot_override_switch.async_turn_on()

        hot_override_switch.coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = hot_override_switch.coordinator.hass.config_entries.async_update_entry.call_args
        options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
        assert options[SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL] is True


class TestCoverWeatherHotOverrideSwitchToggle:
    """Test CoverWeatherHotExternalControlSwitch turn on/off behavior."""

    async def test_turn_off_persists_false(self, cover_hot_override_switch) -> None:
        """Test that turning the switch OFF persists False to config options."""

        cover_hot_override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await cover_hot_override_switch.async_turn_off()

        cover_hot_override_switch.coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = cover_hot_override_switch.coordinator.hass.config_entries.async_update_entry.call_args
        options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
        assert options[f"cover.test_cover_{COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"] is False


class TestWeatherSunnyOverrideSwitchRemoval:
    """Test WeatherSunnyExternalControlSwitch cleanup on entity removal."""

    async def test_reload_unload_does_not_clear_override_key(self, override_switch) -> None:
        """Normal unload during integration reload must not remove the override."""

        entry = override_switch.coordinator.config_entry
        entry.options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] = True
        override_switch.registry_entry = SimpleNamespace(disabled_by=None)
        override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await override_switch.async_will_remove_from_hass()

        override_switch.coordinator.hass.config_entries.async_update_entry.assert_not_called()

    async def test_removal_clears_override_key(self, override_switch) -> None:
        """Test that disabling/removing the entity removes the override key from options."""

        entry = override_switch.coordinator.config_entry
        # Simulate the override being previously set
        entry.options[SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL] = True
        override_switch.registry_entry = SimpleNamespace(disabled_by="user")
        override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await override_switch.async_will_remove_from_hass()

        # Verify async_update_entry was called with the key removed
        override_switch.coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = override_switch.coordinator.hass.config_entries.async_update_entry.call_args
        options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
        assert SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL not in options

    async def test_removal_no_op_when_key_absent(self, override_switch) -> None:
        """Test that removal is a no-op when the override key was never set."""

        override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await override_switch.async_will_remove_from_hass()

        # Should not call async_update_entry when the key isn't present
        override_switch.coordinator.hass.config_entries.async_update_entry.assert_not_called()


class TestWeatherHotOverrideSwitchRemoval:
    """Test WeatherHotExternalControlSwitch cleanup on entity removal."""

    async def test_removal_clears_override_key(self, hot_override_switch) -> None:
        """Test that disabling/removing the entity removes the override key from options."""

        entry = hot_override_switch.coordinator.config_entry
        entry.options[SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL] = True
        hot_override_switch.registry_entry = SimpleNamespace(disabled_by="user")
        hot_override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await hot_override_switch.async_will_remove_from_hass()

        hot_override_switch.coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = hot_override_switch.coordinator.hass.config_entries.async_update_entry.call_args
        options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
        assert SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL not in options


class TestCoverWeatherHotOverrideSwitchRemoval:
    """Test CoverWeatherHotExternalControlSwitch cleanup on entity removal."""

    async def test_removal_clears_override_key(self, cover_hot_override_switch) -> None:
        """Test that disabling/removing the entity removes the per-cover override key from options."""

        entry = cover_hot_override_switch.coordinator.config_entry
        key = f"cover.test_cover_{COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"
        entry.options[key] = True
        cover_hot_override_switch.registry_entry = SimpleNamespace(disabled_by="user")
        cover_hot_override_switch.coordinator.hass.config_entries.async_update_entry = Mock()

        await cover_hot_override_switch.async_will_remove_from_hass()

        cover_hot_override_switch.coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = cover_hot_override_switch.coordinator.hass.config_entries.async_update_entry.call_args
        options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
        assert key not in options


class TestWeatherSunnyOverrideInEngine:
    """Test that the weather sunny override is applied in the automation engine."""

    @pytest.fixture
    def mock_ha_interface(self) -> MagicMock:
        """Create a mock Home Assistant interface."""

        ha_interface = MagicMock()
        ha_interface.get_sun_data = MagicMock(return_value=(180.0, 45.0))
        ha_interface.get_daily_temperature_extrema = AsyncMock(return_value=(28.0, 18.0))
        ha_interface.get_weather_condition = MagicMock(return_value="cloudy")
        return ha_interface

    @pytest.fixture
    def basic_config(self) -> dict[str, Any]:
        """Create a basic test configuration."""

        return {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
        }

    async def test_override_sunny_true_overrides_cloudy_forecast(self, mock_ha_interface, basic_config, mock_logger) -> None:
        """Test that override=True makes weather_sunny=True even when forecast is cloudy."""

        from custom_components.smart_cover_automation.automation_engine import AutomationEngine

        # Set the override in config
        config_with_override = {**basic_config, SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL: True}
        resolved = resolve(basic_config)

        engine = AutomationEngine(
            resolved=resolved,
            config=config_with_override,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        sensor_data, message = await engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.weather_sunny is True

    async def test_override_sunny_false_overrides_sunny_forecast(self, mock_ha_interface, basic_config, mock_logger) -> None:
        """Test that override=False makes weather_sunny=False even when forecast is sunny."""

        from custom_components.smart_cover_automation.automation_engine import AutomationEngine

        # Forecast returns sunny, but override says not sunny
        mock_ha_interface.get_weather_condition.return_value = "sunny"
        config_with_override = {**basic_config, SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL: False}
        resolved = resolve(basic_config)

        engine = AutomationEngine(
            resolved=resolved,
            config=config_with_override,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        sensor_data, message = await engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.weather_sunny is False

    async def test_no_override_uses_forecast(self, mock_ha_interface, basic_config, mock_logger) -> None:
        """Test that without an override, the forecast is used normally."""

        from custom_components.smart_cover_automation.automation_engine import AutomationEngine

        # No override key in config
        resolved = resolve(basic_config)
        engine = AutomationEngine(
            resolved=resolved,
            config=basic_config,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        # Forecast is cloudy → should be not sunny
        mock_ha_interface.get_weather_condition.return_value = "cloudy"
        sensor_data, message = await engine._gather_sensor_data()
        assert sensor_data is not None
        assert sensor_data.weather_sunny is False

        # Change forecast to sunny → should now be sunny
        mock_ha_interface.get_weather_condition.return_value = "sunny"
        sensor_data, message = await engine._gather_sensor_data()
        assert sensor_data is not None
        assert sensor_data.weather_sunny is True

    async def test_override_logs_message(self, mock_ha_interface, basic_config, mock_logger) -> None:
        """Test that an active override logs an info message."""

        from custom_components.smart_cover_automation.automation_engine import AutomationEngine

        config_with_override = {**basic_config, SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL: True}
        resolved = resolve(basic_config)

        engine = AutomationEngine(
            resolved=resolved,
            config=config_with_override,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        await engine._gather_sensor_data()

        # Verify the override was logged
        mock_logger.debug.assert_any_call(
            "Current weather condition: %s (source: %s)",
            "sunny",
            "external control",
        )


class TestWeatherHotOverrideInEngine:
    """Test that the weather hot override is applied in the automation engine."""

    @pytest.fixture
    def mock_ha_interface(self) -> MagicMock:
        """Create a mock Home Assistant interface."""

        ha_interface = MagicMock()
        ha_interface.get_sun_data = MagicMock(return_value=(180.0, 45.0))
        ha_interface.get_daily_temperature_extrema = AsyncMock(return_value=(18.0, 16.0))
        ha_interface.get_weather_condition = MagicMock(return_value="cloudy")
        return ha_interface

    @pytest.fixture
    def basic_config(self) -> dict[str, Any]:
        """Create a basic test configuration."""

        return {
            ConfKeys.COVERS.value: ["cover.test"],
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD.value: 20.0,
            ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD.value: 15.0,
        }

    async def test_override_hot_true_overrides_cool_forecast(self, mock_ha_interface, basic_config, mock_logger) -> None:
        """Test that override=True makes temp_hot=True even when forecast is cool."""

        from custom_components.smart_cover_automation.automation_engine import AutomationEngine

        config_with_override = {**basic_config, SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL: True}
        resolved = resolve(basic_config)

        engine = AutomationEngine(
            resolved=resolved,
            config=config_with_override,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        sensor_data, message = await engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is True

    async def test_override_hot_false_overrides_hot_forecast(self, mock_ha_interface, basic_config, mock_logger) -> None:
        """Test that override=False makes temp_hot=False even when forecast is hot."""

        from custom_components.smart_cover_automation.automation_engine import AutomationEngine

        mock_ha_interface.get_daily_temperature_extrema.return_value = (28.0, 18.0)
        config_with_override = {**basic_config, SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL: False}
        resolved = resolve(basic_config)

        engine = AutomationEngine(
            resolved=resolved,
            config=config_with_override,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        sensor_data, message = await engine._gather_sensor_data()

        assert sensor_data is not None
        assert sensor_data.temp_hot is False

    async def test_override_logs_message(self, mock_ha_interface, basic_config, mock_logger) -> None:
        """Test that an active hot override logs a debug message."""

        from custom_components.smart_cover_automation.automation_engine import AutomationEngine

        config_with_override = {**basic_config, SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL: True}
        resolved = resolve(basic_config)

        engine = AutomationEngine(
            resolved=resolved,
            config=config_with_override,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        await engine._gather_sensor_data()

        mock_logger.debug.assert_any_call(
            "Current weather temperature state: %s (source: %s, daily_max=%s, daily_min=%s, max_threshold_met=%s, min_threshold_met=%s)",
            "hot",
            "external control",
            18.0,
            16.0,
            False,
            True,
        )
