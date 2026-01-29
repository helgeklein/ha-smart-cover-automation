"""Parameterized tests for all Binary Sensor entities.

This module contains comprehensive tests for all binary sensor entities in the integration,
using parameterization to avoid code duplication while maintaining thorough coverage.

Coverage target: binary_sensor.py (all binary sensor entity classes)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, cast

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.binary_sensor import (
    CloseCoversAfterSunsetBinarySensor,
    LockActiveSensor,
    NighttimeBlockOpeningBinarySensor,
    StatusBinarySensor,
    TempHotBinarySensor,
    WeatherSunnyBinarySensor,
)
from custom_components.smart_cover_automation.binary_sensor import (
    async_setup_entry as async_setup_entry_binary_sensor,
)
from custom_components.smart_cover_automation.const import (
    BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET,
    BINARY_SENSOR_KEY_LOCK_ACTIVE,
    BINARY_SENSOR_KEY_NIGHTTIME_BLOCK_OPENING,
    BINARY_SENSOR_KEY_STATUS,
    BINARY_SENSOR_KEY_TEMP_HOT,
    BINARY_SENSOR_KEY_WEATHER_SUNNY,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import CoordinatorData, IntegrationConfigEntry

if TYPE_CHECKING:
    pass


# Binary sensor configuration for parameterized tests
BINARY_SENSOR_CONFIGS = [
    {
        "id": "status",
        "class": StatusBinarySensor,
        "key": BINARY_SENSOR_KEY_STATUS,
        "translation_key": BINARY_SENSOR_KEY_STATUS,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "icon": None,
        "entity_index": 0,  # Position in async_setup_entry list
        "type": "coordinator_state",  # is_on when coordinator fails
        "state_tests": [
            {"name": "coordinator_success", "coordinator_success": True, "expected_is_on": False},
            {"name": "coordinator_failure", "coordinator_success": False, "expected_is_on": True},
        ],
    },
    {
        "id": "close_covers_after_sunset",
        "class": CloseCoversAfterSunsetBinarySensor,
        "key": BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET,
        "translation_key": BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": None,
        "icon": "mdi:weather-sunset",
        "entity_index": 1,
        "type": "config_boolean",  # is_on = config value
        "config_key": "close_covers_after_sunset",
        "state_tests": [
            {"name": "enabled", "config_value": True, "expected_is_on": True},
            {"name": "disabled", "config_value": False, "expected_is_on": False},
        ],
    },
    {
        "id": "nighttime_block_opening",
        "class": NighttimeBlockOpeningBinarySensor,
        "key": BINARY_SENSOR_KEY_NIGHTTIME_BLOCK_OPENING,
        "translation_key": BINARY_SENSOR_KEY_NIGHTTIME_BLOCK_OPENING,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": None,
        "icon": "mdi:weather-night",
        "entity_index": 2,
        "type": "config_boolean",
        "config_key": "nighttime_block_opening",
        "state_tests": [
            {"name": "enabled", "config_value": True, "expected_is_on": True},
            {"name": "disabled", "config_value": False, "expected_is_on": False},
        ],
    },
    {
        "id": "temp_hot",
        "class": TempHotBinarySensor,
        "key": BINARY_SENSOR_KEY_TEMP_HOT,
        "translation_key": BINARY_SENSOR_KEY_TEMP_HOT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": None,
        "icon": "mdi:thermometer-alert",
        "entity_index": 3,
        "type": "data_boolean",  # is_on from coordinator.data
        "data_key": "temp_hot",
        "state_tests": [
            {"name": "true", "data_value": True, "expected_is_on": True},
            {"name": "false", "data_value": False, "expected_is_on": False},
            {"name": "no_data", "data_value": None, "expected_is_on": False},
            {"name": "missing_key", "data_value": "missing", "expected_is_on": False},
        ],
    },
    {
        "id": "weather_sunny",
        "class": WeatherSunnyBinarySensor,
        "key": BINARY_SENSOR_KEY_WEATHER_SUNNY,
        "translation_key": BINARY_SENSOR_KEY_WEATHER_SUNNY,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": None,
        "icon": "mdi:weather-sunny",
        "entity_index": 4,
        "type": "data_boolean",
        "data_key": "weather_sunny",
        "state_tests": [
            {"name": "true", "data_value": True, "expected_is_on": True},
            {"name": "false", "data_value": False, "expected_is_on": False},
            {"name": "no_data", "data_value": None, "expected_is_on": False},
            {"name": "missing_key", "data_value": "missing", "expected_is_on": False},
        ],
    },
    {
        "id": "lock_active",
        "class": LockActiveSensor,
        "key": BINARY_SENSOR_KEY_LOCK_ACTIVE,
        "translation_key": BINARY_SENSOR_KEY_LOCK_ACTIVE,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "device_class": BinarySensorDeviceClass.LOCK,
        "icon": None,
        "entity_index": 5,
        "type": "lock_state",  # is_on = NOT coordinator.is_locked (inverted for HA lock semantics)
        "state_tests": [
            {"name": "unlocked", "lock_mode": "unlocked", "expected_is_on": True},
            {"name": "hold_position", "lock_mode": "hold_position", "expected_is_on": False},
            {"name": "force_open", "lock_mode": "force_open", "expected_is_on": False},
            {"name": "force_close", "lock_mode": "force_close", "expected_is_on": False},
        ],
    },
]


#
# test_binary_sensor_entity_properties
#
@pytest.mark.parametrize("sensor_config", BINARY_SENSOR_CONFIGS, ids=[cfg["id"] for cfg in BINARY_SENSOR_CONFIGS])
async def test_binary_sensor_entity_properties(mock_hass_with_spec, mock_config_entry_basic, sensor_config: dict[str, Any]) -> None:
    """Test that binary sensor has correct entity properties.

    Verifies that the binary sensor is properly initialized with:
    - Correct entity description
    - Proper translation key
    - Icon (if applicable)
    - Entity category
    - Device class (if applicable)

    Coverage target: binary_sensor.py (all binary sensor entity classes)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the entity by index
    entity = captured[sensor_config["entity_index"]]
    assert isinstance(entity, sensor_config["class"])

    # Verify entity description properties
    assert entity.entity_description.key == sensor_config["key"]
    assert entity.entity_description.translation_key == sensor_config["translation_key"]
    assert entity.entity_description.entity_category == sensor_config["entity_category"]

    # Verify device class if specified
    if sensor_config["device_class"] is not None:
        assert entity.entity_description.device_class == sensor_config["device_class"]

    # Verify icon if specified
    if sensor_config["icon"] is not None:
        assert entity.entity_description.icon == sensor_config["icon"]

    # Verify unique_id format
    assert entity.unique_id == f"{mock_config_entry_basic.entry_id}_{sensor_config['key']}"


#
# test_binary_sensor_translation_key
#
@pytest.mark.parametrize("sensor_config", BINARY_SENSOR_CONFIGS, ids=[cfg["id"] for cfg in BINARY_SENSOR_CONFIGS])
async def test_binary_sensor_translation_key(mock_hass_with_spec, mock_config_entry_basic, sensor_config: dict[str, Any]) -> None:
    """Test that binary sensor has translation_key attribute set for state translations.

    This verifies that binary sensors have the translation_key attribute properly
    set, which is required for entity state translations (e.g., "Yes/No" instead of "On/Off").

    Coverage target: binary_sensor.py (IntegrationBinarySensor base class)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the entity by index
    entity = captured[sensor_config["entity_index"]]

    # Verify translation_key attribute exists and matches
    assert hasattr(entity, "translation_key"), f"Entity {sensor_config['key']} missing translation_key attribute"
    assert entity.translation_key == sensor_config["translation_key"], (
        f"Entity {sensor_config['key']} has mismatched translation_key: {entity.translation_key} != {sensor_config['translation_key']}"
    )


#
# test_binary_sensor_availability
#
@pytest.mark.parametrize("sensor_config", BINARY_SENSOR_CONFIGS, ids=[cfg["id"] for cfg in BINARY_SENSOR_CONFIGS])
async def test_binary_sensor_availability(mock_hass_with_spec, mock_config_entry_basic, sensor_config: dict[str, Any]) -> None:
    """Test that sensor inherits availability from coordinator.

    Verifies that the sensor's availability follows the coordinator's state.

    Coverage target: binary_sensor.py (inherited from IntegrationEntity)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the entity by index
    entity = captured[sensor_config["entity_index"]]

    # Test when coordinator is available
    coordinator.last_update_success = True
    assert entity.available is True

    # Test when coordinator is unavailable
    coordinator.last_update_success = False
    assert entity.available is False


#
# test_binary_sensor_setup_count
#
async def test_binary_sensor_setup_count(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that binary sensor platform creates all expected entities.

    Verifies that async_setup_entry creates exactly 6 binary sensor entities.

    Coverage target: binary_sensor.py async_setup_entry function
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Binary sensor platform should expose exactly 6 entities
    assert len(captured) == 6


#
# Helper function to create state test ID
#
def _state_test_id(sensor_config: dict[str, Any], state_test: dict[str, Any]) -> str:
    """Generate pytest test ID for state tests."""
    return f"{sensor_config['id']}-{state_test['name']}"


#
# test_coordinator_state_sensor_states
#
@pytest.mark.parametrize(
    "sensor_config,state_test",
    [(config, state) for config in BINARY_SENSOR_CONFIGS if config["type"] == "coordinator_state" for state in config["state_tests"]],
    ids=lambda params: _state_test_id(*params) if isinstance(params, tuple) else str(params),
)
async def test_coordinator_state_sensor_states(
    mock_hass_with_spec, mock_config_entry_basic, sensor_config: dict[str, Any], state_test: dict[str, Any]
) -> None:
    """Test coordinator state sensors (e.g., StatusBinarySensor).

    These sensors derive their is_on state from the coordinator's health status.

    Coverage target: binary_sensor.py StatusBinarySensor.is_on property
    """
    # Create coordinator with specified success state
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = state_test["coordinator_success"]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the entity by index
    entity = captured[sensor_config["entity_index"]]
    assert isinstance(entity, sensor_config["class"])

    # Verify is_on state
    assert entity.is_on == state_test["expected_is_on"]


#
# test_config_boolean_sensor_states
#
@pytest.mark.parametrize(
    "sensor_config,state_test",
    [(config, state) for config in BINARY_SENSOR_CONFIGS if config["type"] == "config_boolean" for state in config["state_tests"]],
    ids=lambda params: _state_test_id(*params) if isinstance(params, tuple) else str(params),
)
async def test_config_boolean_sensor_states(
    mock_hass_with_spec, mock_config_entry_basic, sensor_config: dict[str, Any], state_test: dict[str, Any]
) -> None:
    """Test config boolean sensors (e.g., CloseCoversAfterSunsetBinarySensor).

    These sensors derive their is_on state from configuration values.

    Coverage target: binary_sensor.py CloseCoversAfterSunsetBinarySensor.is_on,
                     NighttimeBlockOpeningBinarySensor.is_on properties
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Set config value
    mock_config_entry_basic.options[sensor_config["config_key"]] = state_test["config_value"]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the entity by index
    entity = captured[sensor_config["entity_index"]]
    assert isinstance(entity, sensor_config["class"])

    # Verify is_on state
    assert entity.is_on == state_test["expected_is_on"]


#
# test_data_boolean_sensor_states
#
@pytest.mark.parametrize(
    "sensor_config,state_test",
    [(config, state) for config in BINARY_SENSOR_CONFIGS if config["type"] == "data_boolean" for state in config["state_tests"]],
    ids=lambda params: _state_test_id(*params) if isinstance(params, tuple) else str(params),
)
async def test_data_boolean_sensor_states(
    mock_hass_with_spec, mock_config_entry_basic, sensor_config: dict[str, Any], state_test: dict[str, Any]
) -> None:
    """Test data boolean sensors (e.g., TempHotBinarySensor, WeatherSunnyBinarySensor).

    These sensors derive their is_on state from coordinator.data values.
    Tests cover: true, false, no data (None), and missing key scenarios.

    Coverage target: binary_sensor.py TempHotBinarySensor.is_on,
                     WeatherSunnyBinarySensor.is_on properties
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Setup coordinator data based on test case
    if state_test["data_value"] is None:
        # Test case: coordinator.data is None
        coordinator.data = None  # type: ignore[attr-defined]
    elif state_test["data_value"] == "missing":
        # Test case: coordinator.data exists but key is missing
        coordinator.data = CoordinatorData(covers={})  # type: ignore[attr-defined]
    else:
        # Test case: coordinator.data has the key with a specific value
        data_kwargs = {"covers": {}, sensor_config["data_key"]: state_test["data_value"]}
        coordinator.data = CoordinatorData(**data_kwargs)  # type: ignore[attr-defined]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the entity by index
    entity = captured[sensor_config["entity_index"]]
    assert isinstance(entity, sensor_config["class"])

    # Verify is_on state
    assert entity.is_on == state_test["expected_is_on"]


#
# test_lock_state_sensor_states
#
@pytest.mark.parametrize(
    "sensor_config,state_test",
    [(config, state) for config in BINARY_SENSOR_CONFIGS if config["type"] == "lock_state" for state in config["state_tests"]],
    ids=lambda params: _state_test_id(*params) if isinstance(params, tuple) else str(params),
)
async def test_lock_state_sensor_states(
    mock_hass_with_spec, mock_config_entry_basic, sensor_config: dict[str, Any], state_test: dict[str, Any]
) -> None:
    """Test lock state sensor (LockActiveSensor).

    This sensor reports the lock state with inverted logic:
    - is_on=True means unlocked (lock is open in HA terminology)
    - is_on=False means locked (lock is closed/active)

    Coverage target: binary_sensor.py LockActiveSensor.is_on property
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Set lock mode
    mock_config_entry_basic.options["lock_mode"] = state_test["lock_mode"]

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the entity by index
    entity = captured[sensor_config["entity_index"]]
    assert isinstance(entity, sensor_config["class"])

    # Verify is_on state (inverted logic for HA lock semantics)
    assert entity.is_on == state_test["expected_is_on"]


#
# test_status_sensor_stores_unique_id_in_coordinator
#
async def test_status_sensor_stores_unique_id_in_coordinator(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that StatusBinarySensor stores its unique_id in the coordinator.

    This is required for logbook integration to identify the status sensor.

    Coverage target: binary_sensor.py StatusBinarySensor.__init__
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Wire coordinator into runtime_data
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the binary sensor platform
    await async_setup_entry_binary_sensor(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Verify that the coordinator has the status sensor unique_id stored
    assert hasattr(coordinator, "status_sensor_unique_id")
    assert coordinator.status_sensor_unique_id == f"{mock_config_entry_basic.entry_id}_{BINARY_SENSOR_KEY_STATUS}"
