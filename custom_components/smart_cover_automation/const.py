"""
Constants for smart_cover_automation.

Logging Information:
- INFO includes automation decisions and cover actions
- Set log level to WARNING for configuration issues
- Set log level to ERROR for system failures

Note: Detailed cover position/evaluation calculations are not logged by default.

To enable verbose logging, either use the integration's Options (Verbose logging)
or add this to your configuration.yaml:
logger:
  logs:
    custom_components.smart_cover_automation: debug
"""

from logging import getLogger
from typing import Final

LOGGER: Final = getLogger(__package__)

DOMAIN: Final = "smart_cover_automation"

# Window azimuth (degrees)
COVER_AZIMUTH: Final[str] = "cover_azimuth"

# Sensor attribute keys (public API of Automation Status sensor)
ATTR_AUTOMATION_ENABLED: Final[str] = "automation_enabled"  # Whether the automation is currently enabled
ATTR_COVERS_NUM_TOTAL: Final[str] = "covers__num_total"  # Total number of configured covers
ATTR_COVERS_NUM_MOVED: Final[str] = "covers_num_moved"  # Number of covers adjusted in the last cycle
ATTR_MIN_POSITION_DELTA: Final[str] = "min_position_delta"  # Minimum position change (%) required to move
ATTR_TEMP_HYSTERESIS: Final[str] = "temp_hysteresis"  # Temperature hysteresis (°C) to prevent oscillation
ATTR_TEMP_SENSOR_ENTITY_ID: Final[str] = "temp_sensor_entity_id"  # Entity ID of the temperature sensor
ATTR_TEMP_MIN_THRESH: Final[str] = "temp_min_thresh"  # Minimum temperature threshold (°C)
ATTR_TEMP_MAX_THRESH: Final[str] = "temp_max_thresh"  # Maximum temperature threshold (°C)
ATTR_TEMP_CURRENT: Final[str] = "temp_current"  # Current measured temperature (°C)
ATTR_SUN_ELEVATION: Final[str] = "sun_elevation"  # Current sun elevation (°)
ATTR_SUN_ELEVATION_THRESH: Final[str] = "sun_elevation_thresh"  # Minimum elevation (°) to consider direct sun
ATTR_SUN_AZIMUTH: Final[str] = "sun_azimuth"  # Current sun azimuth (°)

# Translation keys used by config flows and tests (centralize to avoid magic strings)
ERROR_INVALID_COVER: Final[str] = "invalid_cover"
ERROR_INVALID_TEMPERATURE_RANGE: Final[str] = "invalid_temperature_range"
ERROR_REQUIRED_WITH_MAX_TEMPERATURE: Final[str] = "required_with_max_temperature"
ERROR_REQUIRED_WITH_MIN_TEMPERATURE: Final[str] = "required_with_min_temperature"
ERROR_INVALID_CONFIG: Final[str] = "invalid_config"

ABORT_SINGLE_INSTANCE_ALLOWED: Final[str] = "single_instance_allowed"

# Home Assistant sun entity and attribute keys (centralize to avoid magic strings)
SUN_ENTITY_ID: Final[str] = "sun.sun"
SUN_ATTR_ELEVATION: Final[str] = "elevation"
SUN_ATTR_AZIMUTH: Final[str] = "azimuth"

# Coordinator data keys and values (internal but shared across modules/tests)
KEY_BODY: Final[str] = "body"
KEY_CURRENT_POSITION: Final[str] = "current_position"
KEY_DESIRED_POSITION: Final[str] = "desired_position"
KEY_COMBINED_STRATEGY: Final[str] = "combined_strategy"
STRATEGY_AND: Final[str] = "and"
