# Smart Cover Automation for Home Assistant

A Home Assistant integration that intelligently automates your window covers using a combined temperature + sun position strategy.

## Features

- Combined automation: Merges temperature and sun logic and chooses the more closed position
- Per-cover window azimuth: Configure each window's facing as an angle (0–359°)
- Configurable behavior: temperature hysteresis, minimum position delta, sun elevation threshold, and maximum closure
- Supports multiple covers with different orientations
- Works with any cover entity that supports open/close or position control
   - If a cover supports position (set_cover_position), partial closure is used
   - If it supports only open/close, actions fall back to those services
- Automation Status sensor: Live summary of combined inputs and per-cover outcomes

## Installation

1. Add this repository to HACS
2. Install the "Smart Cover Automation" integration
3. Restart Home Assistant
4. Add the integration from the HA integrations page

## Configuration

The integration provides an Options flow (in the integration's Configure dialog) so you can tune behavior without editing YAML:

- Enabled: Global on/off switch for all automation logic
- Minimum temperature: Open when cooler than this
- Maximum temperature: Close when hotter than this
- Temperature sensor: Override the sensor entity used for temperature contribution
- Temperature hysteresis: Degrees C around thresholds to avoid oscillation
- Minimum position delta: Ignore tiny position changes to reduce chatter
- Sun elevation threshold: Elevation where sun logic starts acting (defaults to 20°)
- Maximum closure: Cap on how far to close on direct sun (defaults to 100%)
- Per-cover window azimuth: 0–359° angle each cover/window faces

### How the combined automation works

The integration computes a desired position from both temperature and sun, then applies the more closed result (after a minimum-delta guard):

1) Temperature contribution
- If current temperature > maximum: close (block heat)
- If current temperature < minimum: open (allow heat)
- If current temperature within [min, max]: maintain position
- A configurable hysteresis band reduces oscillation around thresholds

2) Sun contribution
- You configure the azimuth (0–359°) each cover/window faces (e.g., South = 180°)
- Below elevation threshold (default 20°): open fully (let light in)
- At/above threshold: compute angle between sun azimuth and window azimuth
   - If angle < tolerance (default 90°, strict): close to `100 - max_closure` (0 if max_closure=100)
   - Else: open fully (sun not directly hitting this window)
- Maximum closure is configurable (default 100%)

3) Final decision
- The automation takes the most closed of the two contributions
- If the change is smaller than the minimum position delta, it's ignored to prevent chatter

Notes:
- Per-cover direction values are numeric azimuths; legacy string directions are not used
- Sun-only covers with missing/invalid direction are skipped

#### Direction Angles (examples)
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
   - Sun contribution closes fully (subject to maximum closure); temperature may reinforce or keep it closed

- **South window in morning**:
   - Sun is east (~90°)
   - Sun contribution opens fully as sun isn't hitting window; temperature contribution may keep it closed if too hot

- **East-facing window**:
   - Morning: Closes as sun shines directly
   - Afternoon: Opens as sun moves west

- **Any window at dawn/dusk**:
   - Sun elevation is low
   - Sun contribution opens fully to maximize natural light

The automation maintains comfort by:
1. Letting in light when sun is low
2. Blocking direct sunlight to prevent heat gain
3. Allowing indirect light through partially closed covers
4. Opening covers when sun moves away from the window
5. Respecting room temperature limits using hysteresis to avoid flapping

### Automation Status Sensor

An additional sensor named "Automation Status" summarizes the current combined inputs and recent results, for example:

- Combined: `Temp 22.5°C in [21.0–24.0] • Sun elev 35.0°, az 180° • moves 1/2`
- Disabled: `Disabled`

Attributes include:
- enabled, automation_type, covers_total, covers_moved
- min_temperature, max_temperature, temperature_hysteresis, min_position_delta
- sun_elevation_threshold, sun elevation/azimuth
- A per-cover snapshot of inputs and desired/current positions for visibility

## Usage

1. Install and add the integration
2. Select covers to automate
3. Configure minimum and maximum temperature thresholds
4. Enter the azimuth for each cover (0–359°, e.g., South=180)
5. Optionally adjust: elevation threshold, maximum closure, hysteresis, and minimum position delta

The integration will handle the combined logic automatically.

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
[INFO] Initializing Smart Cover Automation coordinator: type=combined, covers=['cover.bedroom', 'cover.living_room']
[DEBUG] Starting initial coordinator refresh
[INFO] Smart Cover Automation integration setup completed
```

#### Combined Automation Decisions
```
[INFO] Combined: temp=25.3°C (min=21.0, max=24.0), sun elev=35.2°, az=180.1°, threshold=20.0°
[DEBUG] Cover cover.south_window: window_azimuth=180°, current_pos=100
[INFO] Cover cover.south_window: Sun hitting window (angle=0.1° < 90°) → desired 0; temp contribution → desired 0 → final 0
[INFO] Setting cover cover.south_window position from 100 to 0
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
