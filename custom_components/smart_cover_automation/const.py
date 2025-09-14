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

from datetime import timedelta
from logging import getLogger
from typing import Final

LOGGER: Final = getLogger(__package__)

DOMAIN: Final = "smart_cover_automation"
INTEGRATION_NAME: Final = "Smart Cover Automation"

# Per-cover configuration key suffixes
COVER_SFX_AZIMUTH: Final[str] = "cover_azimuth"  # Cover/window azimuth (°)

# Sensor attribute keys (exposed on the automation status sensor)
SENSOR_ATTR_AUTOMATION_ENABLED: Final[str] = "automation_enabled"  # Whether the automation is currently enabled
SENSOR_ATTR_COVERS_NUM_TOTAL: Final[str] = "covers__num_total"  # Total number of configured covers
SENSOR_ATTR_COVERS_NUM_MOVED: Final[str] = "covers_num_moved"  # Number of covers adjusted in the last cycle
SENSOR_ATTR_COVERS_MAX_CLOSURE_POS: Final[str] = "covers_max_closure_pos"  # Maximum closure position (%) when sun is hitting
SENSOR_ATTR_COVERS_MIN_POSITION_DELTA: Final[str] = "covers_min_position_delta"  # Minimum position change (%) required to move
SENSOR_ATTR_TEMP_CURRENT: Final[str] = "temp_current"  # Current measured temperature (°C)
SENSOR_ATTR_TEMP_HOT: Final[str] = "temp_hot"  # Whether the current temperature is above the threshold
SENSOR_ATTR_TEMP_HYSTERESIS: Final[str] = "temp_hysteresis"  # Temperature hysteresis (°C) to prevent oscillation
SENSOR_ATTR_TEMP_SENSOR_ENTITY_ID: Final[str] = "temp_sensor_entity_id"  # Entity ID of the temperature sensor
SENSOR_ATTR_TEMP_THRESHOLD: Final[str] = "temp_threshold"  # Temperature threshold (°C)
SENSOR_ATTR_SUN_ELEVATION: Final[str] = "sun_elevation"  # Current sun elevation (°)
SENSOR_ATTR_SUN_ELEVATION_THRESH: Final[str] = "sun_elevation_threshold"  # Minimum elevation (°) to consider direct sun
SENSOR_ATTR_SUN_AZIMUTH: Final[str] = "sun_azimuth"  # Current sun azimuth (°)

# Cover attribute keys (exposed on each cover entity)
# Prefix with "sca_" to avoid potential conflicts with other integrations
COVER_ATTR_ERROR: Final[str] = "sca_cover_error"  # Whether an error occurred for this cover
COVER_ATTR_COVER_AZIMUTH: Final[str] = "sca_cover_azimuth"  # Cover/window azimuth (°)
COVER_ATTR_POSITION_DESIRED: Final[str] = "sca_cover_desired_position"  # Desired cover position (%)
COVER_ATTR_SUN_AZIMUTH_DIFF: Final[str] = "sca_sun_azimuth_diff"  # Difference between sun azimuth and cover azimuth (°)
COVER_ATTR_SUN_HITTING: Final[str] = "sca_sun_hitting"  # Whether the sun is hitting the window

# Translation keys used by config flows and tests
ERROR_INVALID_COVER: Final[str] = "invalid_cover"
ERROR_INVALID_CONFIG: Final[str] = "invalid_config"

ABORT_SINGLE_INSTANCE_ALLOWED: Final[str] = "single_instance_allowed"

# Coordinator data keys and values (internal but shared across modules/tests)
KEY_BODY: Final[str] = "body"

# Home Assistant string literals
HA_SUN_ENTITY_ID: Final[str] = "sun.sun"
HA_SUN_ATTR_ELEVATION: Final[str] = "elevation"
HA_SUN_ATTR_AZIMUTH: Final[str] = "azimuth"
HA_OPTIONS: Final = "options"

# Home Assistant cover positions
COVER_POS_FULLY_OPEN: Final = 100
COVER_POS_FULLY_CLOSED: Final = 0

# Coordinator
UPDATE_INTERVAL: Final = timedelta(seconds=60)
