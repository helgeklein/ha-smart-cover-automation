---
layout: default
title: Cover Protection (Wind, Hail)
nav_order: 9
description: "Cover Protection from Wind and Hail with Smart Cover Automation for Home Assistant."
permalink: /cover-protection/
---

# Cover Protection System With Multiple Triggers (Wind, Hail, ...)

## Description

Many types of covers need to be protected from strong winds. In some countries, insurance require covers to be protected from hail. Additional constraints may be relevant for your specific scenario.

This practical guide shows how to implement a simple but effective system that allows multiple different triggers to lock covers in fully opened position while requiring all of the triggers to be in a safe state before unlocking.

## Requirements

### Wind Sensor

Wind protection requires up-to-date local wind speed data; a weather station is ideal. If you don't have local hardware to measure wind speed, you can use [Open-Meteo's free online service](https://open-meteo.com/en/docs?hourly=&current=wind_gusts_10m,wind_speed_10m). It updates every 15 minutes, which is excellent for a free service. You should, however, incorporate a safety margin in your thresholds - and use the wind gusts metric instead of wind speed.

You can find a Home Assistant sensor configuration for Open-Meteo wind speed data below.

## Implementation

### Lock Counter

Create a **counter helper** (Settings → Devices & Services → Helpers → Create helper → Counter):

- **Name:** `SCA cover lock counter`
- **Minimum:** 0
- **Maximum:** 99
- **Initial:** 0

### Increment Lock Counter

To add protection from one source (e.g., wind), create an **automation** (Settings → Automations & scenes → Create automation):

Configure the trigger (when):

- Select **Entity** → **Numeric state**
- **Entity:** select your wind speed/gusts entity
- **Lower limit:** `fixed number`
- **Above:** (enter your covers' maximum supported wind speed - or a lower number to have a safety margin)

Example: `When Open-Meteo: Wind Gusts Current is above 60`

Configure the action (then do):

- **Helpers** → **Counter** → **Increment**
- **Target:** `SCA cover lock counter`

Example: `Counter 'Increment' on SCA cover lock counter`

**Save** the automation as `SCA cover wind lock`.

### Decrement Lock Counter

For each increment automation configured above, add an **automation** that decrements the counter:

Configure the trigger (when):

- Select **Entity** → **Numeric state**
- **Entity:** select your wind speed/gusts entity
- **Upper limit:** `fixed number`
- **Below:** (enter a lower number than the maximum you configured above)

Example: `When Open-Meteo: Wind Gusts Current is below 50`

Configure the action (then do):

- **Helpers** → **Counter** → **Decrement**
- **Target:** `SCA cover lock counter`

Example: `Counter 'Decrement' on SCA cover lock counter`

**Save** the automation as `SCA cover wind unlock`.

### Lock/Unlock Action

Add an **automation** that controls Smart Cover Automation lock mode depending on the lock counter. Paste the following YAML or replicate it in the UI:

```yaml
alias: SCA cover lock automation
description: ""
triggers:
  - trigger: state
    entity_id:
      - counter.sca_cover_lock_counter
conditions: []
actions:
  - choose:
      - conditions:
          - condition: numeric_state
            entity_id: counter.sca_cover_lock_counter
            above: 0
        sequence:
          - action: smart_cover_automation.set_lock
            metadata: {}
            data:
              lock_mode: force_open
    default:
      - action: smart_cover_automation.set_lock
        metadata: {}
        data:
          lock_mode: unlocked
mode: single
```

## Test

To test the automation, go to **Developer Tools** → **States** and manually set the wind gusts sensor to a value that's higher than your threshold.

## Wind Gusts and Speed Sensors via Open-Meteo

Here's a sample implementation of wind speed and gusts sensors via REST API calls to Open-Meteo. Paste the following into `configuration.yaml`:

```yaml
rest:
  # Open-Meteo sensor for current wind speed and gusts at home location
  # The data is updated ever 15 minutes at the quarter hour (00:00, 00:15, 00:30, 00:45)
  # Documentation: https://open-meteo.com/en/docs?hourly=&current=wind_gusts_10m,wind_speed_10m
  - resource_template: "https://api.open-meteo.com/v1/forecast?latitude={{ state_attr('zone.home', 'latitude') }}&longitude={{ state_attr('zone.home', 'longitude') }}&current=wind_speed_10m,wind_gusts_10m&wind_speed_unit=kmh"
    scan_interval: 60  # 1 minute
    sensor:
      - name: "Open-Meteo: Wind Speed Current"
        unique_id: open_meteo_wind_speed_current
        value_template: "{{ value_json.current.wind_speed_10m }}"
        unit_of_measurement: "km/h"
        device_class: wind_speed
        state_class: measurement

      - name: "Open-Meteo: Wind Gusts Current"
        unique_id: open_meteo_wind_gusts_current
        value_template: "{{ value_json.current.wind_gusts_10m }}"
        unit_of_measurement: "km/h"
        device_class: wind_speed
        state_class: measurement
```
