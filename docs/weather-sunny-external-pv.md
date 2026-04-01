---
layout: default
title: "Weather: Sunny? via PV Output"
nav_order: 10
description: "How to determine whether it is sunny from your photovoltaic power output."
permalink: /weather-sunny-external-pv/
---

# How to Determine Whether It Is Sunny from Photovoltaic Power Output

## Description

If you have a photovoltaic installation, you can use its current power output as an indicator for sunshine.

Using a fixed watt threshold is too simplistic because clear-sky PV output depends strongly on the sun's elevation above the horizon. A practical approximation is to estimate the current clear-sky power generation (i.e., the potential maximum) from the sun elevation and then compare the actual PV power against that estimate.

This guide shows how to implement that logic in Home Assistant and then feed the resulting sunny/not-sunny signal into Smart Cover Automation via its **Weather: sunny? (external control)** switch.

The model intentionally ignores azimuth. That makes it simple and often good enough if your PV system has a broad exposure.

## Requirements

- A PV system whose power curve is reasonably smooth and has a single broad peak on a sunny day.
- A Home Assistant sensor that reports your current PV power generation in watts.
- The Home Assistant `sun` integration enabled so that `sun.sun` provides the current elevation.
- Smart Cover Automation installed.
- The Smart Cover Automation entity **Weather: sunny? (external control)** enabled.

This setup works best if your PV system is not heavily shaded by nearby buildings or trees.

## Implementation

### Formula

Estimate the *current* clear-sky maximum PV power with this formula:

`P_max(alpha) = P_peak * sin(alpha)^k`

where:

- `alpha` is the sun elevation above the horizon
- `P_peak` is the absolute clear-sky maximum power of your PV system
- `k` is a shape factor

Then calculate the current normalized PV percentage as:

`PV% = 100 * P_current / max(P_max(alpha), P_floor)`

The minimum reference power `P_floor` avoids unrealistic percentages close to sunrise and sunset, where the theoretical output is near zero but your inverter may still report a small non-zero value.

Recommended starting values:

- `P_peak`: highest power your PV system generates on sunny days in watts
- `k`: `1.35`
- Minimum sun elevation for the clear-sky estimate: `3°`
- Minimum sun elevation for the sunny decision: `8°`
- `P_floor`: `300 W`
- Sunny threshold: `50%`

You should calibrate `P_peak`, `k`, and the sunny threshold from a few clear days of your own data (see tips below).

### Template Sensors

Paste the following into `configuration.yaml`.

Replace `sensor.your_pv_power_generation` with your PV power entity. Also adjust `peak_power_w`, `exponent` (`k` in the formula), and the thresholds to match your installation.

{% raw %}
```yaml
template:
  - sensor:
      - name: "PV Clear-Sky Power Estimate"
        unique_id: pv_clear_sky_power_estimate
        unit_of_measurement: "W"
        device_class: power
        state_class: measurement
        state: >
          {% set elevation_deg = state_attr('sun.sun', 'elevation') | float(0) %}
          {% set peak_power_w = 6000 %}
          {% set exponent = 1.35 %}
          {% set min_elevation_deg = 3 %}
          {% set deg_to_rad = 0.017453292519943295 %}
          {% if elevation_deg <= min_elevation_deg %}
            0
          {% else %}
            {{ (peak_power_w * ((sin(elevation_deg * deg_to_rad)) ** exponent)) | round(0) }}
          {% endif %}

      - name: "PV Utilization"
        unique_id: pv_utilization
        unit_of_measurement: "%"
        state_class: measurement
        state: >
          {% set current_power_w = states('sensor.your_pv_power_generation') | float(0) %}
          {% set estimated_max_w = states('sensor.pv_clear_sky_power_estimate') | float(0) %}
          {% set minimum_reference_power_w = 300 %}
          {% if estimated_max_w <= 0 %}
            0
          {% else %}
            {% set reference_power_w = [estimated_max_w, minimum_reference_power_w] | max %}
            {{ ([100, (100 * current_power_w / reference_power_w)] | min) | round(0) }}
          {% endif %}

  - binary_sensor:
      - name: "PV Sunny"
        unique_id: pv_sunny
        device_class: light
        delay_on:
          minutes: 5
        delay_off:
          minutes: 10
        state: >
          {% set elevation_deg = state_attr('sun.sun', 'elevation') | float(0) %}
          {% set sunny_threshold_percent = 50 %}
          {% set min_decision_elevation_deg = 8 %}
          {% set pv_utilization_percent = states('sensor.pv_utilization') | float(0) %}
          {{ elevation_deg >= min_decision_elevation_deg and pv_utilization_percent >= sunny_threshold_percent }}
```
{% endraw %}

This creates three entities:

- **PV Clear-Sky Power Estimate:** estimated maximum current PV power for the present sun elevation.
- **PV Utilization:** current PV generation as a percentage of the estimated potential maximum for the present sun elevation.
- **PV Sunny:** debounced binary sensor that reports whether it is sunny enough according to your threshold. The `delay_on` and `delay_off` settings stabilize the sensor and avoid flapping when a cloud passes over, for example.

### Connect the Result to Smart Cover Automation

Smart Cover Automation does not read the template binary sensor directly. Instead, enable its entity **Weather: sunny? (external control)** and drive that switch from the template binary sensor.

Create an automation in Home Assistant and paste the following YAML. Replace `switch.smart_cover_automation_weather_sunny_external_control` with the actual entity ID of your Smart Cover Automation switch.

```yaml
alias: SCA weather sunny external control from PV
description: ""
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.pv_sunny
conditions: []
actions:
  - choose:
      - conditions:
          - condition: state
            entity_id: binary_sensor.pv_sunny
            state: "on"
        sequence:
          - action: switch.turn_on
            metadata: {}
            target:
              entity_id: switch.smart_cover_automation_weather_sunny_external_control
    default:
      - action: switch.turn_off
        metadata: {}
        target:
          entity_id: switch.smart_cover_automation_weather_sunny_external_control
mode: single
```

### Calibration

To improve accuracy, calibrate the constants from your own data:

- Wait for a mostly cloudless day.
- In Home Assistant's History viewer, add the actual power generation and the PV clear-sky estimate.
- The estimate's graph should trace the general outline of the actual power generation graph.
- If the estimate's graph is overall too low, increase `peak_power_w` (and vice-versa).
- If the estimate's graph is too low in the morning and evening, decrease `exponent` slightly (and vice-versa).
- Adjust `sunny_threshold_percent` until the **PV Sunny** sensor matches your local observation.

Typical useful ranges:

- `peak_power_w`: your system-specific value
- `exponent`: `1.2` to `1.5`
- `sunny_threshold_percent`: `40` to `80`
- `minimum_reference_power_w`: `200` to `500`

## Test

To test the setup:

1. Verify that **PV Clear-Sky Power Estimate** rises and falls smoothly through the day.
2. Check that **PV Utilization** is high on clear days and low during cloudy periods.
3. Confirm that **PV Sunny** does not flap rapidly when passing clouds move through.
4. Enable Smart Cover Automation's **Weather: sunny? (external control)** entity and verify that the switch follows `binary_sensor.pv_sunny`.

If the sunny state flips too often around sunrise or sunset, raise either `min_decision_elevation_deg` or `minimum_reference_power_w`.

