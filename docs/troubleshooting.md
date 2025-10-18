---
layout: default
title: Troubleshooting
nav_order: 5
description: "Common issues and solutions for Smart Cover Automation for Home Assistant."
permalink: /troubleshooting/
---

# Troubleshooting Guide

This guide helps resolve issues with the Smart Cover Automation integration.

## Monitoring the Integration from the UI

### Activity Logbook

All cover movements are logged in Home Assistant's [activity logbook](https://www.home-assistant.io/integrations/logbook/). Fully translated, of course.

### Sensors

The integration comes with the following sensors that help you understand the integration's inner workings:

- **Status:** Overall status returned by the last automation update.
- **Sun azimuth:** Current sun azimuth (angle from north).
- **Sun elevation:** Current sun elevation (angle above the horizon).
- **Temperature: today's maximum:** Maximum (expected) temperature of the current day. Derived from the configured weather forecast sensor.
- **Temperature: threshold:** The configured temperature at which the automation starts closing covers to protect from heat.
- **Weather: hot day?:** Is the maximum temperature of the current day expected to rise above the configured threshold temperature?
- **Weather: sunny?:** Is the day expected to be at least partly sunny? Derived from the configured weather forecast sensor.

## Debugging

### Enable Verbose Logging

Make sure to enable verbose (debug) logging when analyzing a problem. This can be done via the UI (see the [Configuration Guide]({{ '/configuration/' | relative_url }}))

### Log File Location

In the file system, you can find the **Home Assistant Core** log at `config/home-assistant.log`. It includes the log messages from this integration (filter for `smart_cover_automation`).

In the UI, you can find the same log at **Settings** → **Systems** → **Logs**.

## Getting Help

### Before Seeking Help

1. **Enable verbose logging** and reproduce the issue.
1. **Check the logs** to understand what's going on.
1. **Document your configuration** and the exact problem.

### Where to Get Help

1. **Documentation:** Review all sections of this documentation.
1. **GitHub Issues:** [Report a bug](https://github.com/helgeklein/ha-smart-cover-automation/issues).
1. **Home Assistant Community:** [Join a forum discussion](https://community.home-assistant.io/).
