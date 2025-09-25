---
layout: default
title: Configuration
nav_order: 3
description: "Configuration guide for Smart Cover Automation for Home Assistant."
permalink: /configuration/
---

# Configuration Guide

This guide covers how to configure the Smart Cover Automation integration after installation.

After initial setup, you can modify settings:

1. Go to **Settings** → **Devices & Services**.
2. Find **Smart Cover Automation**.
3. Click **Configure**.

## Configuration Options

### Cover Selection

Choose which covers to include in the automation.

### Weather Integration

The integration needs a weather provider to determine if the sun is shining and if it's going to be a hot day.

### Available Options

TODO

### Per-Cover Settings

TODO

## Entities Created

TODO: VERIFY

The integration creates several entities for monitoring and control:

### Switches

- `switch.smart_cover_automation` - Master enable/disable

### Sensors

- `sensor.smart_cover_automation_status` - Current automation status
- `sensor.smart_cover_automation_last_action` - Last action taken
- `binary_sensor.smart_cover_automation_active` - Automation active state

### Binary Sensors

TODO

## Example Configurations

TODO

## Next Steps

After configuration, see the [Troubleshooting Guide]({{ '/troubleshooting/' | relative_url }}) for common issues and solutions.