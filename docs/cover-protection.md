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

The key idea is that each protection source keeps its own safe/unsafe state. That avoids counter drift when a single source crosses the upper threshold more than once before it finally crosses the lower threshold.

## Requirements

### Wind Sensor

Wind protection requires up-to-date local wind speed data; a weather station is ideal. If you don't have local hardware to measure wind speed, you can use [Open-Meteo's free online service](https://open-meteo.com/en/docs?hourly=&current=wind_gusts_10m,wind_speed_10m). It updates every 15 minutes, which is excellent for a free service. You should, however, incorporate a safety margin in your thresholds - and use the wind gusts metric instead of wind speed.

You can find a Home Assistant sensor configuration for Open-Meteo wind speed data below.

## Implementation

### Per-Source Protection State

Create one **toggle helper** per protection source (Settings → Devices & Services → Helpers → Create helper → Toggle), e.g.:

- **Name:** `SCA cover protection wind: status`
- **Name:** `SCA cover protection hail: status`
- Add one more toggle for each additional source

Each toggle represents whether that source is currently unsafe.

### Control Each Source Status With Hysteresis

For each protection source, create a single automation that turns its toggle on at the upper threshold and off at the lower threshold.

Example for wind gusts:

{% raw %}
```yaml
alias: "SCA cover protection wind: controller"
description: "Control wind protection status with hysteresis."
triggers:
  - trigger: numeric_state
    entity_id: sensor.open_meteo_wind_gusts_current
    above: 60
    id: unsafe
  - trigger: numeric_state
    entity_id: sensor.open_meteo_wind_gusts_current
    below: 50
    id: safe
conditions: []
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: unsafe
        sequence:
          - action: input_boolean.turn_on
            target:
              entity_id: input_boolean.sca_cover_protection_wind_status
    default:
      - action: input_boolean.turn_off
        target:
          entity_id: input_boolean.sca_cover_protection_wind_status
mode: single
```
{% endraw %}

This is idempotent: if wind goes to `65`, back to `55`, then to `65` again, the helper is simply turned on again and no state drift occurs. It only turns off after the wind drops below `50`.

Create equivalent controller automations for hail or any other protection source, each writing to its own helper.

### Aggregate All Protection Sources

Create one template binary sensor that is on whenever any protection source is active:

{% raw %}
```yaml
template:
  - binary_sensor:
      - name: "SCA cover protection active"
        unique_id: sca_cover_protection_active
        device_class: safety
        state: >
          {{
            is_state('input_boolean.sca_cover_protection_wind_status', 'on')
            or is_state('input_boolean.sca_cover_protection_hail_status', 'on')
          }}
```
{% endraw %}

If you only have wind protection, keep just the wind line. If you add more sources later, extend the `or` expression.

### Lock/Unlock Action

Add an automation that controls Smart Cover Automation lock mode from the aggregate protection sensor. Paste the following YAML or replicate it in the UI:

{% raw %}
```yaml
alias: SCA cover lock automation
description: ""
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.sca_cover_protection_active
conditions: []
actions:
  - choose:
      - conditions:
          - condition: state
            entity_id: binary_sensor.sca_cover_protection_active
            state: "on"
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
{% endraw %}

## Test

To test the automation, go to **Developer Tools** → **States** and manually set the wind gusts sensor to values above and below your thresholds.

You should see:

- `input_boolean.sca_cover_protection_wind_status` turn on above the upper threshold
- `input_boolean.sca_cover_protection_wind_status` stay on while the value remains between the thresholds
- `binary_sensor.sca_cover_protection_active` stay on while any source helper is on
- Smart Cover Automation remain locked until all source helpers are off

## Wind Gusts and Speed Sensors via Open-Meteo

Here's a sample implementation of wind speed and gusts sensors via REST API calls to Open-Meteo. Paste the following into `configuration.yaml`:

{% raw %}
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
{% endraw %}
