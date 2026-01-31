---
layout: default
title: Troubleshooting
nav_order: 6
description: "Common issues and solutions for Smart Cover Automation for Home Assistant."
permalink: /troubleshooting/
---

# Troubleshooting Guide

This guide helps resolve issues with the Smart Cover Automation integration.

## Monitoring the Integration from the UI

### Activity Logbook

All cover movements are logged in Home Assistant's [activity logbook](https://www.home-assistant.io/integrations/logbook/). Fully translated, of course.

Filter the logbook for entries from this integration's instances by selecting `Smart Cover Automation` as device (or whatever name you chose for your instances).

### Sensors

The integration comes with the following sensors that help you understand the integration's inner workings:

- **Evening closure: enabled?** When enabled, covers will be closed a certain time after sunset.
- **Evening closure: delay** Time to wait after sunset before closing the covers.
- **Lock status**: Whether lock mode is enabled or disabled.
- **Nighttime: block opening?** Whether to block automatic cover opening during nighttime (when the sun is below the horizon).
- **Status:** Overall status returned by the last automation update.
- **Sun azimuth:** Current sun azimuth (angle from north).
- **Sun elevation:** Current sun elevation (angle above the horizon).
- **Temperature: today's maximum:** Maximum (expected) temperature of the current day. Derived from the configured weather forecast sensor.
- **Temperature: heat threshold:** The configured temperature at which the automation starts closing covers to protect from heat.
- **Time range: disabled:** Start and end of a configured time interval during which the automation is disabled. `Off` it this is not configured.
- **Weather: hot?** Is today's forecast maximum temperature expected to rise above the configured threshold temperature?
  - After 16:00, tomorrow's forecast maximum temperature is used instead of today's.
- **Weather: sunny?** Is the day expected to be at least partly sunny? Derived from the configured weather forecast sensor.

## Debugging

### Enable Verbose Logging

Make sure to enable verbose (debug) logging when analyzing a problem. This can be done via the UI (see the [Configuration Guide]({{ '/configuration-wizard/' | relative_url }})).

Note that verbose logging is enabled per integration instance. This facilitates troubleshooting in a multi-instance setup as you'll only see verbose messages from the instance(s) you're interested in.

### Log File Location

You can find the **Home Assistant Core** log at **Settings** → **Systems** → **Logs**.

### Log Message Format

- **Timestamp:** e.g., `2026-01-31 17:20:22.174`
- **Severity:** e.g., `DEBUG`
- **HA thread name:** e.g., `(MainThread)`
- **Integration instance:** e.g., `[custom_components.smart_cover_automation.ABC12]`
- **Cover entity:** e.g., `[cover.kitchen]` (logged only when the message pertains to a cover)
- **Log message:** the actual log message, e.g., `Current weather condition: partlycloudy`

As you can see above, the integration instance field contains the last five characters of the instance's entry ID that logged the message (`ABC12` in the example). This makes it easy to distinguish between messages from multiple instances.

## Getting Help

### Before Seeking Help

1. **Enable verbose logging** and reproduce the issue.
1. **Check the logs** to understand what's going on.
1. **Document your configuration** and the exact problem.

### Where to Get Help

1. **Documentation:** Review all sections of this documentation.
1. **GitHub Issues:** [Report a bug](https://github.com/helgeklein/ha-smart-cover-automation/issues).
1. **Home Assistant Community:** [Join a forum discussion](https://community.home-assistant.io/).
