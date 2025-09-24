---
layout: default
title: Troubleshooting
nav_order: 4
description: "Common issues and solutions for HA Smart Cover Automation."
permalink: /troubleshooting/
---

# Troubleshooting Guide

This guide helps resolve common issues with the Smart Cover Automation integration.

## Common Issues

### Installation Problems

#### Integration Not Found After Installation

**Symptoms:**
- Integration doesn't appear in the add integration list
- Error: "Integration not found"

**Solutions:**
1. **Restart Home Assistant** completely (not just reload)
2. **Verify file location:**
   ```
   config/custom_components/smart_cover_automation/
   ├── __init__.py
   ├── manifest.json
   └── ... (other files)
   ```
3. **Check file permissions** (should be readable by Home Assistant user)
4. **Clear browser cache** and try again

#### HACS Installation Fails

**Symptoms:**
- "Repository not found" error
- Download fails

**Solutions:**
1. **Check repository URL:** `https://github.com/helgeklein/ha-smart-cover-automation`
2. **Update HACS** to the latest version
3. **Check internet connectivity** from Home Assistant instance
4. **Try manual installation** as alternative

### Configuration Issues

#### Covers Not Responding to Automation

**Symptoms:**
- Automation appears active but covers don't move
- Manual cover control works fine

**Solutions:**

1. **Check Entity IDs:**
   ```yaml
   # Verify in Developer Tools > States
   # Look for your cover entities
   cover.living_room_blinds
   cover.bedroom_curtains
   ```

2. **Test Cover Functionality:**
   ```yaml
   # Test in Developer Tools > Services
   service: cover.open_cover
   target:
     entity_id: cover.your_cover_name
   ```

3. **Check Automation Status:**
   - Verify `switch.smart_cover_automation` is ON
   - Check `sensor.smart_cover_automation_status` for current state

4. **Review Configuration:**
   - Ensure covers are selected in integration config
   - Check time/weather conditions are met

#### Weather Conditions Not Working

**Symptoms:**
- Time-based automation works, weather-based doesn't
- Weather sensor shows data but automation ignores it

**Solutions:**

1. **Verify Weather Integration:**
   ```yaml
   # Check these entities exist:
   weather.your_weather_provider
   sensor.your_weather_provider_temperature
   ```

2. **Check Weather Entity Attributes:**
   - Go to Developer Tools > States
   - Find your weather entity
   - Verify it has `temperature`, `condition`, etc.

3. **Test Weather Sensitivity:**
   - Lower sensitivity if automation isn't triggering
   - Check temperature thresholds are realistic

### Automation Behavior Issues

#### Covers Moving at Wrong Times

**Symptoms:**
- Covers open/close at unexpected times
- Automation ignores manual overrides

**Solutions:**

1. **Check Time Zone Settings:**
   ```yaml
   # In configuration.yaml
   homeassistant:
     time_zone: Europe/Berlin  # Your timezone
   ```

2. **Review Automation Rules:**
   - Check sunrise/sunset calculations
   - Verify time formats (24-hour vs 12-hour)

3. **Manual Override Settings:**
   - Check override timeout settings
   - Verify `binary_sensor.smart_cover_automation_manual_override`

#### Frequent Position Changes

**Symptoms:**
- Covers constantly adjusting position
- Too sensitive to weather changes

**Solutions:**

1. **Adjust Update Interval:**
   - Increase from default 5 minutes to 10-15 minutes
   - Found in integration options

2. **Modify Weather Sensitivity:**
   - Change from "High" to "Medium" or "Low"
   - Adjust temperature thresholds

3. **Add Minimum Change Threshold:**
   - Configure minimum position change (e.g., 10%)
   - Prevents minor adjustments

## Debugging

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.smart_cover_automation: debug
    custom_components.smart_cover_automation.coordinator: debug
    custom_components.smart_cover_automation.config_flow: debug
```

Then restart Home Assistant and check the logs.

### Useful Log Locations

- **Home Assistant Core:** `config/home-assistant.log`
- **Integration Logs:** Filter for `smart_cover_automation`

### Service Calls for Testing

Test various functions manually:

```yaml
# Test automation status
service: smart_cover_automation.get_status
target:
  entity_id: switch.smart_cover_automation

# Force weather update
service: smart_cover_automation.update_weather

# Test cover movement
service: smart_cover_automation.test_cover_movement
data:
  entity_id: cover.your_cover
  position: 50
```

### State Monitoring

Monitor these entities for debugging:

| Entity | Purpose |
|--------|---------|
| `sensor.smart_cover_automation_status` | Current automation state |
| `sensor.smart_cover_automation_last_action` | Last action performed |
| `binary_sensor.smart_cover_automation_active` | Is automation running |
| `binary_sensor.smart_cover_automation_manual_override` | Manual override active |

## Performance Issues

### High CPU Usage

**Symptoms:**
- Home Assistant becomes slow
- High CPU usage from Python process

**Solutions:**

1. **Increase Update Interval:**
   - Change from 5 minutes to 10-15 minutes
   - Reduces processing frequency

2. **Reduce Weather API Calls:**
   - Use local weather data when possible
   - Cache weather data longer

3. **Limit Cover Count:**
   - Don't automate covers that don't benefit
   - Group similar covers with same rules

### Memory Issues

**Symptoms:**
- Home Assistant restarts frequently
- Out of memory errors

**Solutions:**

1. **Check Entity Count:**
   - Each cover creates multiple entities
   - Consider if all are needed

2. **Review History Settings:**
   - Limit history retention for automation entities
   - Use `recorder` configuration

## Error Messages

### Common Error Messages and Solutions

#### "Cover entity not found"
```
Entity cover.bedroom_blinds not found
```
**Solution:** Check entity ID is correct in Developer Tools > States

#### "Weather integration not available"
```
Weather entity weather.openweathermap not available
```
**Solution:** Ensure weather integration is installed and configured

#### "Invalid time format"
```
Invalid time format in automation rule: 25:00
```
**Solution:** Use valid 24-hour time format (00:00 to 23:59)

#### "Permission denied"
```
Permission denied accessing cover.living_room_blinds
```
**Solution:** Check Home Assistant user permissions for cover entities

## Getting Help

If you can't resolve the issue:

### Before Seeking Help

1. **Check Home Assistant logs** for error messages
2. **Enable debug logging** and reproduce the issue
3. **Document your configuration** and the exact problem
4. **Test with minimal configuration** to isolate the issue

### Where to Get Help

1. **GitHub Issues:** [Report a bug](https://github.com/helgeklein/ha-smart-cover-automation/issues)
2. **Home Assistant Community:** [Forum discussion](https://community.home-assistant.io/)
3. **Documentation:** Review all sections of this documentation

### Information to Include

When reporting issues, include:

- Home Assistant version
- Integration version
- Relevant configuration (sanitized)
- Log messages (with debug enabled)
- Steps to reproduce
- Expected vs actual behavior

## Known Issues

### Current Limitations

- **Weather API Rate Limits:** Some weather providers have request limits
- **Cover Response Time:** Physical covers may have delays
- **Time Zone Changes:** Manual restart may be needed after DST changes

### Planned Improvements

- Better error handling for network issues
- More granular weather condition matching
- Enhanced override detection
- Performance optimizations

---

*Still having issues? [Open an issue on GitHub](https://github.com/helgeklein/ha-smart-cover-automation/issues) with detailed information.*