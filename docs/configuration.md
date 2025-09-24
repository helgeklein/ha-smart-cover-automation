---
layout: default
title: Configuration
nav_order: 3
description: "Complete configuration guide for HA Smart Cover Automation with examples and options."
permalink: /configuration/
---

# Configuration Guide

This guide covers how to configure the Smart Cover Automation integration after installation.

## Initial Setup

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ ADD INTEGRATION"**
3. Search for **"Smart Cover Automation"**
4. Follow the configuration flow

### Basic Configuration Options

During initial setup, you'll configure:

| Option | Description | Required |
|--------|-------------|----------|
| **Integration Name** | Friendly name for this automation instance | Yes |
| **Covers** | Select covers to automate | Yes |
| **Weather Entity** | Weather integration to use for conditions | No |
| **Enable Automation** | Start with automation enabled | No |

## Configuration Options

### Cover Selection

Choose which covers to include in the automation:

```yaml
# Example covers that can be automated
covers:
  - cover.living_room_blinds
  - cover.bedroom_curtains
  - cover.kitchen_roller_shutter
```

### Weather Integration

The integration can work with various weather providers:

- **OpenWeatherMap** (Recommended)
- **Met.no**
- **AccuWeather**
- **Weather Underground**
- Built-in Home Assistant weather

### Automation Rules

#### Time-Based Rules

Set different behaviors for different times:

```yaml
# Example time-based configuration
time_rules:
  morning:
    time: "07:00"
    action: "open"
    position: 100
  evening:
    time: "sunset"
    action: "close"
    position: 0
```

#### Weather-Based Rules

Adjust covers based on weather conditions:

```yaml
# Example weather-based rules
weather_rules:
  sunny:
    temperature_above: 25
    condition: "sunny"
    action: "close"
    position: 30
  rainy:
    condition: "rainy"
    action: "close"
    position: 0
```

## Advanced Configuration

### Options Flow

After initial setup, you can modify settings:

1. Go to **Settings** → **Devices & Services**
2. Find **Smart Cover Automation**
3. Click **"CONFIGURE"**

### Available Options

| Setting | Description | Default |
|---------|-------------|---------|
| **Update Interval** | How often to check conditions (minutes) | 5 |
| **Weather Sensitivity** | How sensitive to weather changes | Medium |
| **Override Manual Control** | Allow manual overrides | True |
| **Night Mode** | Different behavior at night | False |

### Per-Cover Settings

Each cover can have individual settings:

```yaml
# Example per-cover configuration
cover_settings:
  cover.living_room_blinds:
    weather_sensitivity: high
    manual_override_timeout: 60  # minutes
    min_position: 10
    max_position: 90

  cover.bedroom_curtains:
    weather_sensitivity: low
    night_mode: true
    sunrise_offset: -30  # minutes before sunrise
```

## Entities Created

The integration creates several entities for monitoring and control:

### Switches

- `switch.smart_cover_automation` - Master enable/disable
- `switch.smart_cover_automation_weather_mode` - Weather-based control
- `switch.smart_cover_automation_time_mode` - Time-based control

### Sensors

- `sensor.smart_cover_automation_status` - Current automation status
- `sensor.smart_cover_automation_last_action` - Last action taken
- `binary_sensor.smart_cover_automation_active` - Automation active state

### Binary Sensors

- `binary_sensor.smart_cover_automation_manual_override` - Manual override active
- `binary_sensor.smart_cover_automation_weather_alert` - Weather-based alert

## Example Configurations

### Basic Automation

Simple time-based automation:

```yaml
# Open at sunrise, close at sunset
time_rules:
  - time: "sunrise"
    action: "open"
    position: 100
  - time: "sunset"
    action: "close"
    position: 0
```

### Advanced Weather Control

Weather-responsive automation:

```yaml
# Complex weather and time rules
automation_rules:
  - conditions:
      - time_after: "08:00"
      - time_before: "20:00"
      - weather_condition: "sunny"
      - temperature_above: 22
    action: "set_position"
    position: 40

  - conditions:
      - weather_condition: ["rainy", "stormy"]
    action: "close"
    position: 0
```

## Configuration File Location

Settings are stored in:
```
.storage/core.config_entries
```

*Note: Don't edit this file directly. Use the UI configuration instead.*

## Validation and Testing

### Testing Your Configuration

1. **Check Logs**: Monitor `home-assistant.log` for errors
2. **Manual Testing**: Use the service calls to test actions
3. **Automation Testing**: Trigger conditions manually

### Service Calls for Testing

```yaml
# Test opening all covers
service: smart_cover_automation.open_covers
data:
  entity_id: switch.smart_cover_automation

# Test weather response
service: smart_cover_automation.update_weather
```

## Troubleshooting Configuration

### Common Configuration Issues

**Covers not responding**
- Check cover entity IDs are correct
- Verify covers are available and functional
- Check automation is enabled

**Weather conditions not working**
- Ensure weather integration is configured
- Check weather entity provides required attributes
- Verify weather sensitivity settings

**Time-based rules not triggering**
- Check Home Assistant timezone settings
- Verify time format (24-hour vs 12-hour)
- Test with absolute times first

### Debug Configuration

Enable debug logging:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.smart_cover_automation: debug
```

## Next Steps

After configuration, see the [Troubleshooting Guide](troubleshooting) for common issues and solutions.