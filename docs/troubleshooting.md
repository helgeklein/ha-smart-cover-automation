---
layout: default
title: Troubleshooting
nav_order: 4
description: "Common issues and solutions for Smart Cover Automation for Home Assistant."
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

#### HACS Installation Fails

**Symptoms:**

- "Repository not found" error
- Download fails

**Solutions:**

1. **Check repository URL:** `https://github.com/helgeklein/ha-smart-cover-automation`
2. **Update HACS** to the latest version
3. **Check internet connectivity** from Home Assistant instance

## Debugging

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.smart_cover_automation: debug
```

Then restart Home Assistant and check the logs.

### Useful Log Locations

- **Home Assistant Core:** `config/home-assistant.log`
- **Integration Logs:** Filter for `smart_cover_automation`

### State Monitoring

Monitor these entities for debugging:

TODO

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
