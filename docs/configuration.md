---
layout: default
title: Configuration
nav_order: 4
description: "Configuration guide for Smart Cover Automation for Home Assistant."
permalink: /configuration/
---

# Configuration Guide

This guide covers how to configure the Smart Cover Automation integration after installation.

## Configuration Wizard

The integration's settings are managed via a multi-step wizard. To invoke the configuration wizard:

1. Go to **Settings** → **Devices & Services**.
2. Find **Smart Cover Automation**.
3. Click the **gear icon** to open the configuration wizard.

**Notes**

- The configuration wizard can be canceled at any time. When you do that, no changes are made to the configuration.
- The configuration wizard can be invoked as often as needed to inspect the configuration or make changes to it.

**Config Flow vs. Options Flow**

- In more technical terms, the configuration wizard would be called the options flow.
- The integration doesn't use a config flow. This means there's nothing to configure while adding the integration.

### Step 1: Weather Forecast Sensor and Covers to Automate

In the first step of the configuration wizard, choose the following:

#### Weather Forecast Sensor

The integration needs to determine:

- Is the **weather hot** enough to require sun protection?
- Is the **sun** is currently **shining**?

This is done with the help of a weather forecast sensor. Home Assistant provides various weather integrations that should work well. See this [official list of weather integrations](https://www.home-assistant.io/integrations/#weather) and this [community guide to weather integrations](https://community.home-assistant.io/t/definitive-guide-to-weather-integrations/736419/1) for help choosing one.

I've **tested** the following weather integrations successfully:

- [Met.no](https://www.home-assistant.io/integrations/met/)
- [Open-Meteo](https://www.home-assistant.io/integrations/open_meteo/)

To determine if the **weather is hot enough** to require sun protection, the integration needs today's maximum temperature. Unfortunately, some weather forecast services only provide the maximum temperature for the remaining hours of the day. To compensate, this integration switches to the next day's temperature reading starting at 16:00 (afternoon).

The maximum temperature received from the weather forecast service is compared with the temperature threshold (see below). If forecast temperature is above the threshold, the integration considers the weather to be hot.

The integration considers the following current weather conditions as the **sun is shining** (as reported by the weather forecast service):

- sunny
- partlycloudy

#### Covers

Select the covers the integration should automate.

### Step 2: Cover Azimuth

In the second step of the configuration wizard, specify each cover's azimuth, aka the direction, as an angle from north. This is necessary so that the integration can calculate when the sun is shining on a window.

### Step 3: Additional Settings (Optional)

In the third step of the configuration wizard, the following settings can be configured. They don't have to, though, as the defaults should work well enough to get you started.

- **Maximum cover position:** Never close more than this to always let some light in (0 = fully closed, 100 = fully open).
- **Minimum cover position:** Never open more than this to always provide a minimum of shade (0 = fully closed, 100 = fully open).
- **Manual override duration:** How long to skip a cover after it has been moved manually (0 = no skipping).
- **Sun azimuth tolerance:** Maximum horizontal angle at which the sun is considered to be shining on the window (degrees).
- **Minimal sun elevation:** The automation starts operating when the sun's elevation is above this threshold (degrees above horizon).
- **Temperature threshold:** Temperature at which the automation starts closing covers to protect from heat (degrees Celsius).

### Step 4: Per-Cover Max/Min Positions (Optional)

In the fourth step of the configuration wizard, you can specify maximum and minimum positions per cover. If configured, these per-cover settings override the global max/min positions which can be configured in the previous step.

## Switches on the Integration Card

In addition to the abovementioned rather static configuration settings, the integration's behavior can be controlled via switches on the integration card:

- **Enabled:** Enables or disables the automation.
- **Simulation mode:** If enabled, the automation runs through all calculations without actually moving the covers.
- **Verbose logging:** Enables or disabled detailed logging.

## Next Steps

After configuration, see the [Troubleshooting Guide]({{ '/troubleshooting/' | relative_url }}) for common issues and solutions.