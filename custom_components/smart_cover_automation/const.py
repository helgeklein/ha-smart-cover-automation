"""
Constants for smart_cover_automation.

Logging Information:
- Set log level to DEBUG for detailed cover position calculations
- Set log level to INFO for automation decisions and cover actions
- Set log level to WARNING for configuration issues
- Set log level to ERROR for system failures

To enable verbose logging, add this to your configuration.yaml:
logger:
  logs:
    custom_components.smart_cover_automation: debug

Error Handling:
- The integration includes comprehensive error handling for:
  * Missing or invalid temperature sensors
  * Sun integration availability issues
  * Cover entity unavailability
  * Service call failures (cover control)
  * Configuration validation errors
  * Integration setup/teardown failures
- Errors are logged with appropriate detail levels
- Critical errors will prevent automation but allow integration to continue
- Service call failures are logged but don't stop other covers from operating
- All custom exceptions inherit from UpdateFailed for proper coordinator handling
"""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "smart_cover_automation"

# Configuration
CONF_MAX_TEMP = "max_temperature"
CONF_MIN_TEMP = "min_temperature"
CONF_COVERS = "covers"
CONF_SUN_ELEVATION_THRESHOLD = "sun_elevation_threshold"
CONF_COVER_DIRECTION = "cover_direction"
CONF_TEMP_SENSOR = "temperature_sensor"
CONF_ENABLED = "enabled"
CONF_TEMP_HYSTERESIS = "temperature_hysteresis"
CONF_MIN_POSITION_DELTA = "min_position_delta"
CONF_MAX_CLOSURE = "max_closure"

# Defaults
DEFAULT_MAX_TEMP = 24
DEFAULT_MIN_TEMP = 21
DEFAULT_SUN_ELEVATION_THRESHOLD = 20  # degrees
DEFAULT_TEMP_SENSOR = "sensor.temperature"

# Sun position thresholds
AZIMUTH_TOLERANCE = 90  # Window considers sun if within this angle

# Window thresholds
# Default maximum closure percentage when sun directly hits the window.
# 100% means a direct hit will fully close unless overridden in Options.
MAX_CLOSURE = 100

# Behavior tuning
TEMP_HYSTERESIS = 0.5  # degrees Celsius; helps avoid rapid toggling near thresholds
MIN_POSITION_DELTA = (
    5  # percentage points; ignore tiny position changes to avoid chatter
)
