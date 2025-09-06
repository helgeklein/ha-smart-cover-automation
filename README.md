# Smart Cover Automation for Home Assistant

A Home Assistant integration that intelligently automates your window covers based on temperature or sun position.

## Features

- Temperature-based automation: Controls covers based on indoor temperature
- Sun-based automation: Automatically manages covers based on sun position
- Supports multiple covers with different orientations
- Works with any cover entity that supports open/close or position control
   - If a cover supports position (set_cover_position), partial closure is used
   - If it supports only open/close, actions fall back to those services
- Automation Status sensor: Live summary of the current mode and per-cover outcomes

## Installation

1. Add this repository to HACS
2. Install the "Smart Cover Automation" integration
3. Restart Home Assistant
4. Add the integration from the HA integrations page

## Configuration

The integration provides an Options flow (in the integration's Configure dialog) so you can tune behavior without editing YAML:

- Enabled: Global on/off switch for all automation logic
- Temperature sensor: Override the sensor entity used for temperature mode
- Temperature hysteresis: Degrees C around thresholds to avoid oscillation
- Minimum position delta: Ignore tiny position changes to reduce chatter
- Sun elevation threshold: Elevation where sun logic starts acting (defaults to 20°)
- Maximum closure: Cap on how far to close on direct sun (defaults to 90%)
- Per-cover window directions: Cardinal direction each cover/window faces

### Temperature-based Automation

Configure temperature thresholds to automatically manage covers:
- When temperature exceeds maximum: Covers close to block heat
- When temperature falls below minimum: Covers open to allow heat
- When temperature is in range: Maintains current position

Notes:
- You can set the temperature sensor from the integration's Options.
- Hysteresis and minimum position delta are configurable to smooth behavior.

### Sun-based Automation

Intelligently manages covers based on sun position relative to each window:

#### How it Works

1. **Configuration**:
   - Specify which direction each cover/window faces (N, NE, E, SE, S, SW, W, NW)
   - Set sun elevation threshold (default 20°) that determines when covers respond
   - System uses 45° tolerance to determine if sun is hitting a window
   - Maximum closure is configurable (default 90%) to maintain some natural light
   - Direction keys are stored per cover as `<cover_entity_id>_cover_direction`

2. **Automation Logic**:
   ```
   If sun elevation < threshold:
       Open covers fully (let in light when sun is low)
   Else:
       Calculate angle between sun and window direction
       If angle ≤ 45°:
           Close proportionally to how directly sun hits
           (direct hit = 90% closed, glancing = minimal closure)
       Else:
           Open fully (sun not hitting this window)
   ```

3. **Direction Angles**:
   ```
   North = 0°
   Northeast = 45°
   East = 90°
   Southeast = 135°
   South = 180°
   Southwest = 225°
   West = 270°
   Northwest = 315°
   ```

#### Example Scenarios

- **South-facing window at noon**:
  - Sun is directly south (180°)
  - Cover closes to 90% to block direct sunlight

- **South window in morning**:
  - Sun is east (~90°)
  - Cover opens fully as sun isn't hitting window

- **East-facing window**:
  - Morning: Closes as sun shines directly
  - Afternoon: Opens as sun moves west

- **Any window at dawn/dusk**:
  - Sun elevation is low
  - Cover opens fully to maximize natural light

The automation maintains comfort by:
1. Letting in light when sun is low
2. Blocking direct sunlight to prevent heat gain
3. Allowing indirect light through partially closed covers
4. Opening covers when sun moves away from window

### Automation Status Sensor

An additional sensor named "Automation Status" summarizes the current automation mode and recent results, for example:

- Temperature mode: `Temp 22.5°C in [21.0–24.0] • moves 1/2`
- Sun mode: `Sun elev 35.0°, az 180° • moves 1/2`
- Disabled: `Disabled`

Attributes include:
- enabled, automation_type, covers_total, covers_moved
- temperature_hysteresis, min_position_delta
- Mode-specific fields: current/min/max temperature; sun elevation/azimuth and threshold
- A per-cover snapshot of inputs and desired/current positions for visibility

## Usage

1. Install and add the integration
2. Choose automation type (temperature or sun-based)
3. Select covers to automate
4. For temperature automation:
   - Set minimum and maximum temperature thresholds
5. For sun-based automation:
   - Configure which direction each cover faces
   - Optionally adjust the elevation threshold

The integration will handle the rest automatically!

## Troubleshooting & Monitoring

### Enabling Verbose Logging

To understand exactly why covers move to specific positions and troubleshoot issues, enable detailed logging:

```yaml
# Add to configuration.yaml
logger:
  logs:
    custom_components.smart_cover_automation: debug
```

**Log Levels:**
- `debug`: Detailed calculations, cover states, service calls
- `info`: Automation decisions, cover movements, temperature/sun readings
- `warning`: Configuration issues, missing entities
- `error`: System failures, invalid sensors

Update cadence: The coordinator runs every 60 seconds by default.
Coordinator semantics: Exceptions are captured and exposed on `coordinator.last_exception`; they do not propagate to callers of `async_refresh()`.

### What You'll See in the Logs

#### Integration Lifecycle
```
[INFO] Setting up Smart Cover Automation integration
[INFO] Initializing Smart Cover Automation coordinator: type=sun, covers=['cover.bedroom', 'cover.living_room']
[DEBUG] Starting initial coordinator refresh
[INFO] Smart Cover Automation integration setup completed
```

#### Temperature Automation Decisions
```
[INFO] Temperature automation: current=25.3°C, range=21.0-24.0°C
[INFO] Cover cover.bedroom: Too hot (25.3°C > 24.0°C) - closing to block heat (current: 50 → desired: 0)
[INFO] Setting cover cover.bedroom position from 50 to 0
[DEBUG] Setting cover cover.bedroom to position 0 using set_cover_position service
```

#### Sun Automation Decisions
```
[INFO] Sun automation: elevation=35.2°, azimuth=180.1°, threshold=20.0°
[DEBUG] Cover cover.south_window: direction=south (180°), current_pos=100
[INFO] Cover cover.south_window: Sun hitting window (angle=0.1° ≤ 45°) - partial closure factor=1.00, position=10
[INFO] Setting cover cover.south_window position from 100 to 10
```

#### Common Log Messages

**Normal Operation:**
- `"Starting cover automation update"` - Automation cycle begins
- `"Temperature comfortable (...) - maintaining position"` - No change needed
- `"Sun low (...) - opening fully"` - Morning/evening behavior
- `"Sun not hitting window (...) - opening fully"` - Window not in direct sun

**Configuration Issues:**
- `"Cover ... is unavailable"` - Cover entity not responding
- `"Temperature sensor 'sensor.temperature' not found"` - Missing temperature sensor
- `"Cover ...: no direction configured"` - Window direction not set for sun automation
- `"Cover ...: invalid direction '...'"` - Invalid direction value

**System Problems:**
- `"Sun integration not available"` - Sun integration disabled
- `"Invalid temperature reading"` - Sensor data corrupted
- `"Cannot set cover ... position"` - Cover doesn't support position control
 - Service call failures (e.g., `close_cover`) are logged and the cycle continues; other covers still operate.

### Debugging Common Issues

#### Covers Not Moving
1. **Check entity availability:**
   ```
   [WARNING] Cover cover.bedroom is unavailable
   ```
   - Verify cover entity exists and is responsive
   - Check cover device/integration status

2. **Check automation decisions:**
   ```
   [DEBUG] Cover cover.bedroom: no position change needed
   ```
   - Covers already in correct position
   - Temperature/sun conditions don't require changes

#### Temperature Automation Not Working
1. **Verify temperature sensor:**
   ```
   [ERROR] Temperature sensor 'sensor.temperature' not found
   ```
   - Create or configure a temperature sensor entity
   - Ensure it's named `sensor.temperature` or update the code

2. **Check temperature thresholds:**
   ```
   [INFO] Temperature comfortable (22.1°C in range 21-24°C) - maintaining position
   ```
   - Temperature is within comfort range
   - Adjust min/max thresholds if needed

#### Sun Automation Not Working
1. **Check sun integration:**
   ```
   [ERROR] Sun integration not available - sun.sun entity not found
   ```
   - Enable the built-in Sun integration
   - Verify location is configured in Home Assistant

2. **Verify window directions:**
   ```
   [WARNING] Cover ...: no direction configured, skipping sun automation
   ```
   - Configure direction for each cover in the integration settings

3. **Check sun elevation:**
   ```
   [INFO] Cover ...: Sun low (15.2° < 20°) - opening fully
   ```
   - Sun is below threshold - covers open for light
   - Normal behavior during early morning/evening

### Performance Monitoring

The integration updates every 60 seconds by default. Monitor logs to ensure:
- Updates complete successfully
- No error messages appear repeatedly
- Cover movements are reasonable and not excessive

### Getting Support

When reporting issues, please include:
1. Full error messages from logs
2. Your automation configuration
3. Relevant entity states (covers, temperature sensor, sun)
4. Home Assistant version and integration version

Enable debug logging and capture several automation cycles to help diagnose problems.
