# Smart Cover Automation for Home Assistant

A Home Assistant integration that intelligently automates your window covers using a combined temperature + sun position strategy.

## Features

- **Temperature + sun:** Moves only when it's too hot and the sun is hitting the window; supports temp-only or sun-only when configured alone.
- **Exact window direction:** Each window's direction is specified as an angle from north.
- **Configurable behavior:** Temperature hysteresis, minimum position delta, sun elevation threshold, and maximum closure.
- Works with any cover entity that supports open/close or position control:
   - If a cover supports position (`set_cover_position`), partial closure is used.
   - If it supports only open/close, actions fall back to that.
- Automation status sensor: Live summary of inputs and per-cover outcomes.

## Installation

1. Add this repository to HACS
2. Install the **Smart Cover Automation** integration
3. Restart Home Assistant
4. Add the integration from the HA integrations page

## Configuration Options

The integration provides an options flow (in the integration's Configure dialog) so you can tune behavior without editing YAML:

- **Enabled:** Global on/off switch for all automation logic.
- **Minimum temperature:** Open when cooler than this.
- **Maximum temperature:** Close when hotter than this.
- **Temperature sensor:** Override the sensor entity used for temperature contribution.
- **Temperature hysteresis:** Degrees Celsius around thresholds to avoid oscillation.
- **Minimum position delta:** Ignore tiny position changes to reduce chatter.
- **Sun elevation threshold:** Minimum elevation above the horizon where sun logic starts acting (defaults to 20°).
- **Maximum closure:** Cap on how far to close on direct sun (defaults to 100%).
- **Per-cover window azimuth:** 0–359° angle each cover/window faces.

## How the Automation Works

The integration computes a desired position from both temperature and sun:

1) Temperature contribution

- If current temperature > maximum: close (block heat)
- If current temperature < minimum: open (allow heat)
- If current temperature within [min, max]: maintain position
- A configurable hysteresis band reduces oscillation around thresholds

2) Sun contribution

- You configure each window cover's azimuth from north (e.g., south = 180°).
- Sun elevation threshold (angle above the horizon):
    - Below the elevation threshold : open fully (let light in).
    - Above the elevation threshold: compute angle between sun azimuth and window azimuth:
        - If angle < tolerance : close to configured maximum closure position.
        - Else: open fully (sun not directly hitting this window).

3) Final decision

- If both temperature and sun are configured: act only when temperature is hot AND sun is hitting; otherwise maintain position.
- If only temperature is configured: use the temperature decision.
- If only sun is configured: use the sun decision.
- If sun is configured but a cover's direction is invalid/missing: fall back to temperature-only for that cover.
- If the change is smaller than the minimum position delta, it's ignored to prevent chatter.

**Notes:**

- Per-cover direction values are numeric azimuths.
- Sun-only covers with missing/invalid direction are skipped.

### Direction Angles (Examples)

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

### Example Scenarios

- **South-facing window at noon on a cold day**:
   - The sun is directly south (180°).
   - The temperature is below the minimum.
   - The cover remains open to maximize natural light.

- **South-facing window at noon on a hot day**:
   - The sun is directly south (180°).
   - The temperature is above the minimum.
   - The cover closes fully (subject to maximum closure) to block heat.

- **East-facing window**:
   - Morning: Closes as sun shines directly if the temperature is above the minimum.
   - Afternoon: Opens as sun moves west.

- **Any window at dawn/dusk**:
   - Sun elevation is low.
   - Sun contribution opens fully to maximize natural light.

The automation maintains comfort by:

1. Letting in light when sun is low.
2. Blocking direct sunlight to prevent heat gain if it's hot outside.
3. Opening covers when sun moves away from the window.
4. Respecting room temperature limits using hysteresis to avoid flapping.

### Automation Status Sensor

An additional sensor named `Automation Status` summarizes the current inputs and recent results, for example:

- Combined: `Temp 22.5°C in [21.0–24.0] • Sun elev 35.0°, az 180° • moves 1/2`
- Disabled: `Disabled`

## Usage

1. Install and add the integration
2. Select covers to automate
3. Configure minimum and maximum temperature thresholds
4. Enter the azimuth for each cover (0–359°; e.g., south=180)
5. Optionally adjust: elevation threshold, maximum closure, hysteresis, and minimum position delta

## Troubleshooting & Monitoring

### Enabling Verbose Logging

To understand exactly why covers move to specific positions and troubleshoot issues, enable detailed logging:

- Recommended: Toggle "Verbose logging" in the integration's options to enable DEBUG logs for this entry.
- Or enable via YAML globally:

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
[INFO] Initializing Smart Cover Automation coordinator: covers=['cover.bedroom', 'cover.living_room']
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

### Getting Support

When reporting issues, please include:
1. Full error messages from logs
2. Your automation configuration
3. Relevant entity states (covers, temperature sensor, sun)
4. Home Assistant version and integration version

Enable debug logging and capture several automation cycles to help diagnose problems.
