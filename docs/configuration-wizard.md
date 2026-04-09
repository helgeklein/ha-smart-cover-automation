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

This is done with the help of a weather forecast sensor by default (various alternatives exist, see [UI configuration entities]({{ '/ui-configuration-entities/' | relative_url }})).

Home Assistant provides various weather integrations that should work well. See this [official list of weather integrations](https://www.home-assistant.io/integrations/#weather) and this [community guide to weather integrations](https://community.home-assistant.io/t/definitive-guide-to-weather-integrations/736419/1) for help choosing one.

The following weather integrations have been **tested** successfully:

- [Met.no](https://www.home-assistant.io/integrations/met/)
- [Open-Meteo](https://www.home-assistant.io/integrations/open_meteo/)

To determine if the **weather is hot enough** to require sun protection, the integration uses both the daily minimum and maximum temperatures. If both are above their respective [thresholds]({{ '/ui-configuration-entities/#sun--temperature-settings' | relative_url }}), the weather is considered to be hot.

Some weather forecast services only provide minimum/maximum temperatures for the remaining hours of the day. To compensate, this integration switches to the next day's temperature reading starting at 16:00 (afternoon) to determine the maximum, and 30 minutes before sunrise to determine the minimum.

The integration considers the following current weather conditions as the **sun is shining** (as reported by the weather forecast service):

- `sunny`
- `partlycloudy`

### Covers

Select the covers the integration should automate.

## Step 2: Cover Azimuth

In this step of the configuration wizard, specify each cover's azimuth (the direction), as an angle from north. This is necessary so that the integration can calculate when the sun is shining on a window.

There are several online tools available to measure azimuth. [OpenStreetMap Compass](https://osmcompass.com/) works well, as does [SunCalc](https://www.suncalc.org/). You can find instructions for both on [this website](https://doc.forecast.solar/find_your_azimuth).

## Step 3: Max/Min Positions (Optional)

In this step of the configuration wizard, you can specify maximum and minimum positions (0 = fully closed, 100 = fully open). These options can be used to always let some light in and/or always provide a minimum of shade.

The following settings are available:

- **Maximum cover position:** The most closed position the integration moves the cover to during regular operation (e.g., for heat protection).
- **Minimum cover position:** The most open position the integration moves the cover to during regular operation (e.g., to let light in).
- **Cover position for evening closure:** The position the integration moves the cover to for evening closure.

### Global Position Settings

The above position settings are available as global settings that are applied whenever no per-cover setting is configured.

### Per-Cover Overrides

The global positions can be overridden per cover.

## Step 4: Tilt Angle Control (Optional)

In this step of the configuration wizard, you can specify how the tilt angle of covers with adjustable slats is to be controlled. The following options are available:

- **Auto:** Block direct sunlight but allow seeing through as much as possible.
  - Only direct sunlight is blocked (cloudy conditions and the sun's position is taken into account).
  - If the sun is not shining on a window, the slats are kept in open mode to allow indirect light through.
  - Not available in night mode.
- **Manual:** Don't change the user's manual setting.
- **Open:** Keep the slats fully open.
- **Closed:** Keep the slats fully closed.
- **Set value:** Keep the slats at a fixed angle.
- **External:** Set the tilt angle from your own automation.
  - When this mode is selected, the integration creates additional entities that receive the tilt angle.
  - The integration-created entities are fully managed, i.e., they're deleted again if the mode is changed away from `external`.
  - The integration-managed tilt angle entities are available globally as well as per cover, depending on where you configured `external` as tilt angle control mode.
  - The integration only adjusts your covers' tilt angles if the tilt angle entities actually have a valid value (0-100).
  - If both global and per-cover external tilt angle values are specified, the per-cover value takes precedence.

### Global Tilt Modes for Day and Night

The above tilt modes are available in two variants: one applies to operations during the day, the other to the evening closure position.

### Per-Cover Overrides

The global tilt modes can be overridden per cover.

## Step 5: Window Sensors for Lockout Protection (Optional)

In this step of the configuration wizard, you can enable lockout protection by configuring window sensors for each cover. If any window sensor associated with a cover reports that the window is open, the cover won't be closed. This is especially useful for patio or terrace doors with a cover that would block you from re-entering the building if closed.

## Step 6: Time Settings (Optional)

In this step of the configuration wizard, the following settings can be configured:

### Blocked Time Range

Blocked time range allows you to disable the automation in a certain time range, e.g., when you sleep. It delays the cover opening in the morning until the end of the configured time range. So, if you configure the blocked time range as 22:00 to 7:00, the covers will not open before 7 am.


Blocked time range settings:

- **Disable automation in time range:** Enable or disable the blocked time range function.
- **Disable from:** Start time of the time period in which the automation should be inactive.
- **Disable until:** End time of the time period in which the automation should be inactive.

### Evening Closure

Evening closure allows you to automatically close all or a subset of the previously selected covers in the evening, either at a fixed time or with a certain delay after sunset. The same covers become eligible to reopen in the morning if normal automation permits, either at a fixed time, a certain delay after sunrise or at an externally controlled time.

**Notes:**

- The evening closure function is active in a 10 minute time window that starts at the configured point in time. If the integration is not running during that time window, the covers will not be closed.
- Covers closed by the evening closure function stay closed until the specified morning opening time or until the end of the blocked time range - whichever is later.

Evening closure settings:

- **Close covers in the evening:** Enable or disable the evening closure function.
- **Evening closure: mode:** Choose whether to close at a fixed time or relative to sunset.
- **Evening closure: time:** Depending on the selected mode: delay after sunset, or fixed time of day.
- **Morning opening: mode:** Specifies the earliest reopening time for the previously closed covers. Actual reopening only happens if normal automation permits (e.g., heat protection).
  - **Absolute time:** A fixed time of day.
  - **Relative to sunrise:** A specified delay after sunrise.
  - **External:** Set the earliest reopening time from your own automation.
    - The integration creates an additional entity that receives the opening time.
    - This entity is fully managed, i.e., it's deleted again if the mode is changed away from `external`.
    - If this entity has no valid time, the integration cannot determine when to reopen the covers, so they stay closed.
- **Morning opening: time:** Depending on the selected mode: delay after sunrise, or fixed time of day. This setting is ignored if `Morning opening: mode` is `external`.
- **Covers:** Subset of covers to close after sunset.
- **Ignore manual override duration:** When enabled, the evening closure can move selected covers even if a manual override pause is still active.

## Next Steps

After the configuration wizard, take a look at the [UI configuration entities]({{ '/ui-configuration-entities/' | relative_url }}).