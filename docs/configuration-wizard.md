---
layout: default
title: Configuration Wizard
nav_order: 4
description: "Configuration guide part 1 for Smart Cover Automation for Home Assistant."
permalink: /configuration-wizard/
---

# Configuration Wizard

The integration's settings are managed via a multi-step wizard. To invoke the configuration wizard:

1. Go to **Settings** → **Devices & Services**.
2. Find **Smart Cover Automation**.
3. Click the **gear icon** to open the configuration wizard.

**Notes**

- The configuration wizard can be canceled at any time. When you do that, no changes are made to the configuration.
- The configuration wizard can be invoked as often as needed to inspect the configuration or make changes to it.

## Step 1: Weather Forecast Sensor and Covers to Automate

### Weather Forecast Sensor

The integration needs to determine:

- Is the **weather hot** enough to require sun protection?
- Is the **sun** currently **shining**?

This is done with the help of a weather forecast sensor. Home Assistant provides various weather integrations that should work well. See this [official list of weather integrations](https://www.home-assistant.io/integrations/#weather) and this [community guide to weather integrations](https://community.home-assistant.io/t/definitive-guide-to-weather-integrations/736419/1) for help choosing one.

I've **tested** the following weather integrations successfully:

- [Met.no](https://www.home-assistant.io/integrations/met/)
- [Open-Meteo](https://www.home-assistant.io/integrations/open_meteo/)

To determine if the **weather is hot enough** to require sun protection, the integration needs today's maximum temperature. Unfortunately, some weather forecast services only provide the maximum temperature for the remaining hours of the day. To compensate, this integration switches to the next day's temperature reading starting at 16:00 (afternoon).

The maximum temperature received from the weather forecast service is compared with the heat threshold (see below). If the forecast temperature is above the threshold, the integration considers the weather to be hot.

The integration considers the following current weather conditions as the **sun is shining** (as reported by the weather forecast service):

- `sunny`
- `partlycloudy`

### Covers

Select the covers the integration should automate.

## Step 2: Cover Azimuth

In the second step of the configuration wizard, specify each cover's azimuth, aka the direction, as an angle from north. This is necessary so that the integration can calculate when the sun is shining on a window.

There are several online tools available to measure azimuth. [OpenStreetMap Compass](https://osmcompass.com/) works well, as does [SunCalc](https://www.suncalc.org/). [This website](https://doc.forecast.solar/find_your_azimuth) has instructions for both.

## Step 3: Per-Cover Max/Min Positions (Optional)

In the third step of the configuration wizard, you can specify maximum and minimum positions per cover. If configured, these per-cover settings override the global max/min positions which can be configured in the previous step.

## Step 4: Window Sensors for Lockout Protection (Optional)

In the fourth step of the configuration wizard, you can enable lockout protection by configuring window sensors for each cover. If any window sensor associated with a cover reports that the window is open, the cover won't be closed. This is especially useful for patio or terrace doors with a cover that would block you from re-entering the building if closed.

## Step 5: Time Settings (Optional)

In the fifth step of the configuration wizard, the following settings can be configured:

- **Disable cover opening at night:** The automation opens the covers when they needn't be closed for heat protection. By default, this auto-opening doesn't happen at night (when the sun is below the horizon). You can change that behavior by flipping this setting to disabled.

### Blocked Time Range

Blocked time range allows you to disable the automation in a certain time range, e.g., when you sleep.

Blocked time range settings:

- **Disable automation in time range:** Enable or disable the blocked time range function.
- **Disable from:** Start time of the time period in which the automation should be inactive.
- **Disable until:** End time of the time period in which the automation should be inactive.

### Evening Closure

Evening closure allows you to automatically close a subset of the previously selected covers with a certain delay after sunset.

**Note:** The evening closure function is active in a 10 minute time window that starts at the configured point in time (sunset + delay). If the integration is not running during that time window, the covers will not be closed.

Evening closure settings:

- **Close covers after sunset:** Enable or disable the evening closure function.
- **Time delay:** How long to wait after sunset unteil the selected subset of covers are closed.
- **Covers:** Subset of covers to close after sunset.

## Next Steps

After the configuration wizard, take a look at the [UI configuration entities]({{ '/ui-configuration-entities/' | relative_url }}).