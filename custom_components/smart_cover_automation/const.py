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

from logging import getLogger
from typing import Final

LOGGER: Final = getLogger(__package__)

DOMAIN: Final = "smart_cover_automation"

# Configuration
CONF_MIN_TEMP: Final = "min_temperature"
# Backwards-compat key kept for tests; runtime uses Settings field name
CONF_MAX_TEMP: Final = "max_temperature"
CONF_COVERS: Final = "covers"
CONF_SUN_ELEVATION_THRESHOLD: Final = "sun_elevation_threshold"
CONF_COVER_DIRECTION: Final = "cover_direction"
CONF_TEMP_SENSOR: Final = "temperature_sensor"
CONF_ENABLED: Final = "enabled"
CONF_TEMP_HYSTERESIS: Final = "temperature_hysteresis"
CONF_MIN_POSITION_DELTA: Final = "min_position_delta"
CONF_MAX_CLOSURE: Final = "max_closure"
CONF_VERBOSE_LOGGING: Final = "verbose_logging"

# Defaults
DEFAULT_MAX_TEMP: Final = 24
DEFAULT_MIN_TEMP: Final = 21
DEFAULT_SUN_ELEVATION_THRESHOLD: Final = 20  # degrees
DEFAULT_TEMP_SENSOR: Final = "sensor.temperature"
DEFAULT_MAX_CLOSURE: Final[int] = 100
DEFAULT_VERBOSE_LOGGING: Final[bool] = False

# Sun position thresholds
AZIMUTH_TOLERANCE: Final[int] = 90  # Window considers sun if within this angle

# Behavior tuning
TEMP_HYSTERESIS: Final[float] = 0.5  # degrees Celsius; helps avoid rapid toggling near thresholds
MIN_POSITION_DELTA: Final[int] = (
    5  # percentage points; ignore tiny position changes to avoid chatter
)
